"""Central notification dispatcher and scheduler.

All TaskMate notifications flow through this module. It owns:
  * The static NOTIFICATION_TYPES registry (built-in metadata)
  * `fire(type_id, context)` — the public dispatch entry point
  * Scheduled callbacks for time-gated types (bedtime, streak-at-risk, custom)
  * The mobile_app_notification_action listener for tap-to-approve

Other coordinators MUST NOT call notify.* / persistent_notification directly
once this module is in place. They call self.notifications.fire(...).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    NOTIF_TYPE_ALL_CHORES_DONE,
    NOTIF_TYPE_BADGE_EARNED,
    NOTIF_TYPE_BEDTIME_REMINDER,
    NOTIF_TYPE_PENDING_CHORE_APPROVAL,
    NOTIF_TYPE_PENDING_REWARD_CLAIM,
    NOTIF_TYPE_STREAK_AT_RISK,
)
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationTypeMeta:
    id: str
    audience: str            # "child" | "parent" | "both"
    time_gated: bool         # has its own scheduled callback
    per_recipient_time: bool # if True, route.time controls the schedule per recipient
    actionable: bool         # carries Approve/Reject mobile actions
    default_enabled: bool    # default master_enabled state at install


NOTIFICATION_TYPES: list[NotificationTypeMeta] = [
    NotificationTypeMeta(NOTIF_TYPE_BEDTIME_REMINDER,       "child",  True,  True,  False, False),
    NotificationTypeMeta(NOTIF_TYPE_STREAK_AT_RISK,         "child",  True,  False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_ALL_CHORES_DONE,        "both",   False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_BADGE_EARNED,           "both",   False, False, False, True),
    NotificationTypeMeta(NOTIF_TYPE_PENDING_CHORE_APPROVAL, "parent", False, False, True,  True),
    NotificationTypeMeta(NOTIF_TYPE_PENDING_REWARD_CLAIM,   "parent", False, False, True,  True),
]

NOTIFICATION_TYPES_BY_ID: dict[str, NotificationTypeMeta] = {
    t.id: t for t in NOTIFICATION_TYPES
}


class _SafeDict(dict):
    """str.format_map dict that leaves missing keys as `{key}` literal."""
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class NotificationCoordinator:
    """Single dispatcher for all TaskMate notifications."""

    def __init__(self, hass: HomeAssistant, storage) -> None:
        self.hass = hass
        self.storage = storage
        self._scheduled_unsubs: list = []     # cancellation handles for time triggers

    async def fire(self, type_id: str, context: dict[str, Any]) -> None:
        """Dispatch a notification of the given type with the given context."""
        meta = NOTIFICATION_TYPES_BY_ID.get(type_id)
        if meta is None:
            _LOGGER.warning("Unknown notification type %s", type_id)
            return

        cfg = self.storage.get_notification_config(type_id)
        if not cfg.master_enabled:
            self._fire_bus_event(type_id, context, recipients=[])
            return

        recipients_fired: list[str] = []
        message = self._render_template(meta, context)

        for recipient_id, route in cfg.routes.items():
            if not route.enabled:
                continue
            notify_service = self._resolve_notify_service(recipient_id)
            if not notify_service:
                continue
            await self._send_to(notify_service, message, meta, context)
            recipients_fired.append(recipient_id)

        await self._fire_persistent_notification(type_id, message)
        self._fire_bus_event(type_id, context, recipients_fired)

    def _resolve_notify_service(self, recipient_id: str) -> str:
        if recipient_id.startswith("child:"):
            child_id = recipient_id.split(":", 1)[1]
            child = self.storage.get_child(child_id)
            return child.notify_service or "" if child else ""
        if recipient_id.startswith("parent:"):
            for p in self.storage.get_parent_recipients():
                if p.id == recipient_id and p.enabled:
                    return p.notify_service
        return ""

    def _render_template(self, meta: "NotificationTypeMeta", context: dict[str, Any]) -> str:
        # Built-in types use a baked-in default; will be replaced by translations
        # in a later task. For now use a safe English fallback so dispatch works.
        templates = {
            NOTIF_TYPE_BEDTIME_REMINDER:       "{child_name}, you still have chores to do before bedtime.",
            NOTIF_TYPE_STREAK_AT_RISK:         "{child_name}, complete a chore today to keep your {streak}-day streak!",
            NOTIF_TYPE_ALL_CHORES_DONE:        "{child_name} finished every chore today!",
            NOTIF_TYPE_BADGE_EARNED:           "{child_name} earned the {badge_name} badge!",
            NOTIF_TYPE_PENDING_CHORE_APPROVAL: "{child_name} completed '{chore_name}' (+{points} {points_name}) — awaiting approval.",
            NOTIF_TYPE_PENDING_REWARD_CLAIM:   "{child_name} claimed '{reward_name}' ({cost} {points_name}) — awaiting approval.",
        }
        tpl = context.get("message_template") or templates.get(meta.id, "")
        return tpl.format_map(_SafeDict(context))

    async def _send_to(
        self, notify_service: str, message: str,
        meta: "NotificationTypeMeta", context: dict[str, Any],
    ) -> None:
        domain, service = (
            notify_service.split(".", 1) if "." in notify_service
            else ("notify", notify_service)
        )
        if domain != "notify":
            _LOGGER.warning("notify_service must be notify.*, got %s", notify_service)
            return

        data: dict[str, Any] = {"title": "TaskMate", "message": message}
        if meta.actionable:
            entry_id = context.get("entry_id")
            if entry_id:
                data["data"] = {
                    "actions": [
                        {"action": f"TASKMATE_APPROVE_{entry_id}", "title": "Approve"},
                        {"action": f"TASKMATE_REJECT_{entry_id}",  "title": "Reject"},
                    ]
                }
        try:
            await self.hass.services.async_call(domain, service, data, blocking=False)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("notify call failed for %s: %s", notify_service, err)

    async def _fire_persistent_notification(self, type_id: str, message: str) -> None:
        await self.hass.services.async_call(
            "persistent_notification", "create",
            {
                "title": "TaskMate",
                "message": message,
                "notification_id": f"taskmate_{type_id}",
            },
            blocking=False,
        )

    def _fire_bus_event(self, type_id: str, context: dict[str, Any], recipients: list[str]) -> None:
        payload = dict(context)
        payload["recipients"] = recipients
        self.hass.bus.async_fire(f"taskmate_{type_id}", payload)
