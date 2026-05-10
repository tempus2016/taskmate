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
from homeassistant.helpers.event import async_track_time_change

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
        self.coordinator: Any = None

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

    async def handle_mobile_action(self, event) -> None:
        """Route TASKMATE_APPROVE_<id> / TASKMATE_REJECT_<id> mobile actions."""
        action = (event.data or {}).get("action", "")
        if not action.startswith("TASKMATE_"):
            return
        coordinator = getattr(self, "coordinator", None)
        if coordinator is None:
            return

        if action.startswith("TASKMATE_APPROVE_"):
            entry_id = action[len("TASKMATE_APPROVE_"):]
            try:
                await coordinator.async_approve_chore(entry_id)
                return
            except (ValueError, KeyError):
                pass
            try:
                await coordinator.async_approve_reward(entry_id)
            except (ValueError, KeyError):
                _LOGGER.info("Mobile action %s — entry not found", action)
        elif action.startswith("TASKMATE_REJECT_"):
            entry_id = action[len("TASKMATE_REJECT_"):]
            try:
                await coordinator.async_reject_chore(entry_id)
                return
            except (ValueError, KeyError):
                pass
            try:
                await coordinator.async_reject_reward(entry_id)
            except (ValueError, KeyError):
                _LOGGER.info("Mobile action %s — entry not found", action)

    # ------------------------------------------------------------------
    # Scheduler — time-gated callbacks
    # ------------------------------------------------------------------

    async def async_setup_schedules(self) -> None:
        """Cancel any existing time callbacks and register fresh ones from current config.

        Call this on startup AND after any config change that affects schedules
        (e.g. bedtime time edited, custom notification time edited, master toggled).
        """
        for unsub in self._scheduled_unsubs:
            try:
                unsub()
            except Exception:  # noqa: BLE001
                pass
        self._scheduled_unsubs = []

        # Bedtime — per-child time
        cfg = self.storage.get_notification_config("bedtime_reminder")
        if cfg.master_enabled:
            for recipient_id, route in cfg.routes.items():
                if not route.enabled or not route.time:
                    continue
                if not recipient_id.startswith("child:"):
                    continue
                child_id = recipient_id.split(":", 1)[1]
                self._register_at(
                    route.time,
                    self._make_bedtime_callback(child_id),
                )

        # Streak at risk — global cutoff time, fire once per child
        cfg = self.storage.get_notification_config("streak_at_risk")
        if cfg.master_enabled:
            cutoff = self.storage.get_streak_at_risk_cutoff()
            self._register_at(cutoff, self._streak_at_risk_callback)

        # Custom — per-row time
        for custom in self.storage.get_custom_notifications():
            if not custom.enabled:
                continue
            self._register_at(
                custom.time,
                self._make_custom_callback(custom.id),
            )

    def _register_at(self, hhmm: str, callback) -> None:
        try:
            hour, minute = map(int, hhmm.split(":", 1))
        except (ValueError, AttributeError):
            _LOGGER.warning("Invalid time %r — skipping schedule", hhmm)
            return
        unsub = async_track_time_change(
            self.hass, callback, hour=hour, minute=minute, second=0,
        )
        self._scheduled_unsubs.append(unsub)

    def _make_bedtime_callback(self, child_id: str):
        async def _cb(now):
            child = self.storage.get_child(child_id)
            if child is None:
                return
            if not self._has_outstanding_chores_today(child_id):
                return
            await self.fire(
                "bedtime_reminder",
                {"child_name": child.name, "child_id": child_id},
            )
        return _cb

    async def _streak_at_risk_callback(self, now) -> None:
        from homeassistant.util import dt as dt_util
        today = dt_util.now().date().isoformat()
        for child in self.storage.get_children():
            if (child.current_streak or 0) < 2:
                continue
            if child.last_completion_date == today:
                continue
            await self.fire(
                "streak_at_risk",
                {
                    "child_name": child.name,
                    "child_id": child.id,
                    "streak": child.current_streak,
                },
            )

    def _make_custom_callback(self, custom_id: str):
        async def _cb(now):
            from homeassistant.util import dt as dt_util
            n = next(
                (c for c in self.storage.get_custom_notifications() if c.id == custom_id),
                None,
            )
            if n is None or not n.enabled:
                return
            today_bit = 1 << dt_util.now().date().weekday()  # Mon=0
            if not (n.day_mask & today_bit):
                return
            for recipient_id in n.recipient_ids:
                notify_service = self._resolve_notify_service(recipient_id)
                if not notify_service:
                    continue
                child_name = ""
                if recipient_id.startswith("child:"):
                    child = self.storage.get_child(recipient_id.split(":", 1)[1])
                    child_name = child.name if child else ""
                message = n.message_template.format_map(
                    _SafeDict({"child_name": child_name, "time": n.time}),
                )
                service_name = notify_service.split(".", 1)[1] if "." in notify_service else notify_service
                await self.hass.services.async_call(
                    "notify", service_name,
                    {"title": "TaskMate", "message": message},
                    blocking=False,
                )
            self.hass.bus.async_fire(
                "taskmate_custom_notification",
                {"id": n.id, "name": n.name, "recipients": n.recipient_ids},
            )
        return _cb

    # ------------------------------------------------------------------
    # CRUD wrappers — persist + reload schedules as needed
    # ------------------------------------------------------------------

    async def upsert_custom(self, n) -> None:
        self.storage.upsert_custom_notification(n)
        await self.storage.async_save()
        await self.async_setup_schedules()

    async def delete_custom(self, custom_id: str) -> None:
        self.storage.delete_custom_notification(custom_id)
        await self.storage.async_save()
        await self.async_setup_schedules()

    async def upsert_parent(self, p) -> None:
        self.storage.upsert_parent_recipient(p)
        await self.storage.async_save()

    async def delete_parent(self, parent_id: str) -> None:
        self.storage.delete_parent_recipient(parent_id)
        await self.storage.async_save()
        await self.async_setup_schedules()  # in case routes referenced this id

    async def set_route(self, type_id: str, recipient_id: str, route) -> None:
        self.storage.set_notification_route(type_id, recipient_id, route)
        await self.storage.async_save()
        if NOTIFICATION_TYPES_BY_ID.get(type_id) and NOTIFICATION_TYPES_BY_ID[type_id].time_gated:
            await self.async_setup_schedules()

    async def set_master_enabled(self, type_id: str, enabled: bool) -> None:
        self.storage.set_notification_master(type_id, enabled)
        await self.storage.async_save()
        if NOTIFICATION_TYPES_BY_ID.get(type_id) and NOTIFICATION_TYPES_BY_ID[type_id].time_gated:
            await self.async_setup_schedules()

    async def set_streak_cutoff(self, hhmm: str) -> None:
        self.storage.set_streak_at_risk_cutoff(hhmm)
        await self.storage.async_save()
        await self.async_setup_schedules()

    def _has_outstanding_chores_today(self, child_id: str) -> bool:
        """Returns True if the child has at least one chore assigned today
        that has no approved/pending completion yet."""
        from homeassistant.util import dt as dt_util
        today = dt_util.now().date()
        chores = self.storage.get_chores()
        completions = self.storage.get_completions()
        completed_today = {
            c.chore_id for c in completions
            if c.child_id == child_id
            and dt_util.as_local(c.completed_at).date() == today
        }
        for chore in chores:
            if not chore.assigned_to or child_id not in chore.assigned_to:
                continue
            if chore.id in completed_today:
                continue
            return True
        return False
