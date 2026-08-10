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
    DEFAULT_NOTIFICATION_NAV_URL,
    NOTIF_TYPE_ALL_CHORES_DONE,
    NOTIF_TYPE_BADGE_EARNED,
    NOTIF_TYPE_BEDTIME_REMINDER,
    NOTIF_TYPE_CELEBRATION,
    NOTIF_TYPE_FAMILY_GOAL_REACHED,
    NOTIF_TYPE_LEVEL_UP,
    NOTIF_TYPE_MANDATORY_PARENT_ALERT,
    NOTIF_TYPE_MANDATORY_REMINDER,
    NOTIF_TYPE_MONTHLY_REPORT,
    NOTIF_TYPE_PENDING_CHORE_APPROVAL,
    NOTIF_TYPE_PENDING_REWARD_CLAIM,
    NOTIF_TYPE_SEASON_CHAMPION,
    NOTIF_TYPE_STREAK_AT_RISK,
    NOTIF_TYPE_STREAK_MILESTONE,
    NOTIF_TYPE_WEEKLY_DIGEST,
)
from .models import NotificationRoute

_LOGGER = logging.getLogger(__name__)

# Appended to actionable notifications sent to non-mobile_app backends, which
# silently ignore tap actions. Gives those recipients a way to act.
_APPROVE_IN_PANEL_HINT = "Open the TaskMate panel to approve or reject."


def _approval_tag(entry_id: str) -> str:
    """Stable HA companion-app notification tag for an approval (chore/reward).

    Set on the outgoing mobile push so that, once the item is approved or
    rejected, the same tag can be passed to ``clear_notification`` to dismiss
    the alert from the phone. Keyed on the completion/claim id, so each pending
    item owns exactly one push.
    """
    return f"taskmate_approval_{entry_id}"


@dataclass(frozen=True)
class NotificationTypeMeta:
    id: str
    audience: str  # "child" | "parent" | "both"
    time_gated: bool  # has its own scheduled callback
    per_recipient_time: bool  # if True, route.time controls the schedule per recipient
    actionable: bool  # carries Approve/Reject mobile actions
    default_enabled: bool  # default master_enabled state at install


NOTIFICATION_TYPES: list[NotificationTypeMeta] = [
    NotificationTypeMeta(NOTIF_TYPE_BEDTIME_REMINDER, "child", True, True, False, False),
    NotificationTypeMeta(NOTIF_TYPE_STREAK_AT_RISK, "child", True, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_ALL_CHORES_DONE, "both", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_BADGE_EARNED, "both", False, False, False, True),
    NotificationTypeMeta(NOTIF_TYPE_PENDING_CHORE_APPROVAL, "parent", False, False, True, True),
    NotificationTypeMeta(NOTIF_TYPE_PENDING_REWARD_CLAIM, "parent", False, False, True, True),
    NotificationTypeMeta(NOTIF_TYPE_STREAK_MILESTONE, "both", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_LEVEL_UP, "both", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_WEEKLY_DIGEST, "parent", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_CELEBRATION, "both", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_MANDATORY_REMINDER, "child", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_MANDATORY_PARENT_ALERT, "parent", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_MONTHLY_REPORT, "parent", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_SEASON_CHAMPION, "both", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_FAMILY_GOAL_REACHED, "both", False, False, False, False),
]

NOTIFICATION_TYPES_BY_ID: dict[str, NotificationTypeMeta] = {t.id: t for t in NOTIFICATION_TYPES}


def _validate_nav_url(value: str) -> str:
    """Normalise and vet a notification tap target.

    The tap target is opened on the *recipient's* device, so only dashboard
    paths, web URLs and the companion app's noAction sentinel are allowed —
    never intent:// / app:// / homeassistant:// style deep links.
    """
    value = (value or "").strip()
    if value in ("", "noAction"):
        return value
    if value.lower().startswith(("http://", "https://")):
        return value
    if value.startswith("/") and not value.startswith("//") and not any(ord(c) <= 32 or ord(c) == 127 for c in value):
        return value
    raise ValueError("nav_url must be a /path, an http(s) URL, or noAction")


def _parse_hhmm(value: str) -> tuple[int, int] | None:
    """Parse "HH:MM" into (hour, minute); None if blank/malformed."""
    if not value:
        return None
    try:
        hour, minute = map(int, value.split(":", 1))
    except (ValueError, AttributeError):
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def _is_within_quiet_hours(start: str, end: str, now) -> bool:
    """True if ``now`` (a datetime) falls inside the [start, end) HH:MM window.

    Both bounds must be set, else quiet hours are disabled. A start later than
    the end denotes an overnight window (e.g. 20:00-07:00). The end bound is
    exclusive so a window of 07:00-07:00 (equal bounds) is treated as disabled.
    """
    s = _parse_hhmm(start)
    e = _parse_hhmm(end)
    if s is None or e is None or s == e:
        return False
    cur = now.hour * 60 + now.minute
    start_m = s[0] * 60 + s[1]
    end_m = e[0] * 60 + e[1]
    if start_m < end_m:
        return start_m <= cur < end_m
    # Overnight window: active from start through midnight to end.
    return cur >= start_m or cur < end_m


class _SafeDict(dict):
    """str.format_map dict that leaves missing keys as `{key}` literal."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class NotificationCoordinator:
    """Single dispatcher for all TaskMate notifications."""

    def __init__(self, hass: HomeAssistant, storage) -> None:
        self.hass = hass
        self.storage = storage
        self._scheduled_unsubs: list = []  # cancellation handles for time triggers
        self.coordinator: Any = None

    async def fire(
        self,
        type_id: str,
        context: dict[str, Any],
        only_recipients: set[str] | None = None,
    ) -> None:
        """Dispatch a notification of the given type with the given context.

        ``only_recipients`` — if given, restrict delivery to those recipient ids
        (e.g. a single ``child:<id>``). Used for per-child escalation so a
        reminder about one child doesn't fan out to every routed recipient.
        """
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
        nav_url = self._resolve_nav_url(cfg)

        # Multi-parent routing (#687): thin the PARENT recipients down per the
        # configured policy. Child routes are never touched — a reminder for a
        # child must always reach that child.
        allowed_parents = self._route_parents(type_id, cfg, only_recipients)

        for recipient_id, route in cfg.routes.items():
            if recipient_id.startswith("parent:") and recipient_id not in allowed_parents:
                continue
            if not route.enabled:
                continue
            if only_recipients is not None and recipient_id not in only_recipients:
                continue
            if self._child_in_quiet_hours(recipient_id):
                # Do-not-disturb: suppress this child's notifications during
                # their configured quiet-hours window. Parent routes (and the
                # bus event below) are unaffected.
                continue
            notify_service = self._resolve_notify_service(recipient_id)
            if not notify_service:
                continue
            await self._send_to(notify_service, message, meta, context, nav_url)
            recipients_fired.append(recipient_id)

        # NOTE: deliberately no unconditional persistent_notification here.
        # persistent_notification is instance-wide (visible to every HA user,
        # including a child on a kiosk), so firing it for every notification
        # leaked parent-audience messages ("… awaiting approval") to the child
        # who just completed the chore. A persistent notification now happens
        # only when a recipient is explicitly routed to notify.persistent_
        # notification, flowing through _send_to like any other channel.
        self._fire_bus_event(type_id, context, recipients_fired)

    # ── Multi-parent routing (#687) ──────────────────────────────────────

    PARENT_ROUTING_MODES = ("all", "home", "round_robin")

    def parent_routing_mode(self) -> str:
        mode = str(self.storage.get_setting("parent_routing", "all") or "all")
        return mode if mode in self.PARENT_ROUTING_MODES else "all"

    def _parent_is_home(self, recipient_id: str) -> bool:
        """True when this parent's presence entity says they're here.

        No entity configured means "always available" — a parent who hasn't
        set one up shouldn't be silently excluded from every approval.
        """
        parent = next(
            (p for p in self.storage.get_parent_recipients() if p.id == recipient_id),
            None,
        )
        entity_id = (getattr(parent, "presence_entity", "") or "").strip() if parent else ""
        if not entity_id:
            return True
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unavailable", "unknown", None, ""):
            # Fail open: a broken presence sensor must not stop approvals.
            return True
        return str(state.state).lower() in ("home", "on", "true", "present")

    def _route_parents(
        self,
        type_id: str,
        cfg,
        only_recipients: set[str] | None,
    ) -> set[str]:
        """Which parent recipient ids should receive this notification."""
        candidates = [
            rid
            for rid, route in cfg.routes.items()
            if rid.startswith("parent:") and route.enabled and (only_recipients is None or rid in only_recipients)
        ]
        if not candidates:
            return set()

        mode = self.parent_routing_mode()
        if mode == "all":
            return set(candidates)

        if mode == "home":
            at_home = [rid for rid in candidates if self._parent_is_home(rid)]
            # Nobody home: tell everyone rather than nobody. An unseen approval
            # is worse than a redundant buzz.
            return set(at_home or candidates)

        # round_robin — one parent per notification, rotating.
        ordered = sorted(candidates)
        state = self.storage.get_setting("parent_routing_state", {})
        state = dict(state) if isinstance(state, dict) else {}
        last = state.get(type_id)
        try:
            start = ordered.index(last) + 1 if last in ordered else 0
        except ValueError:
            start = 0
        chosen = ordered[start % len(ordered)]
        state[type_id] = chosen
        self.storage.set_setting("parent_routing_state", state)
        return {chosen}

    async def send_test(self, type_id: str) -> list[str]:
        """Send a sample notification of ``type_id`` to its enabled routes.

        Ignores ``master_enabled`` (so a route can be verified before going live),
        prefixes the message with "[TEST] ", and does not emit a bus event.
        Returns the recipient ids that were sent to.
        """
        meta = NOTIFICATION_TYPES_BY_ID.get(type_id)
        if meta is None:
            raise ValueError(f"Unknown notification type {type_id}")
        ctx = {
            "child_name": "Alex",
            "chore_name": "Tidy room",
            "reward_name": "Movie night",
            "badge_name": "Star Helper",
            "points": 10,
            "cost": 50,
            "streak": 7,
            "days": 7,
            "level": 5,
            "tier": 3,
            "message": "Alex reached level 5!",
            "summary": "• Alex: 5 chores, 50 Stars earned",
            "month": "January 2026",
            "goal_name": "Movie night fund",
            "goal_reward": "a family movie night",
            "points_name": self.storage.get_points_name(),
        }
        message = "[TEST] " + self._render_template(meta, ctx)
        cfg = self.storage.get_notification_config(type_id)
        nav_url = self._resolve_nav_url(cfg)
        sent: list[str] = []
        for recipient_id, route in cfg.routes.items():
            if not route.enabled:
                continue
            notify_service = self._resolve_notify_service(recipient_id)
            if not notify_service:
                continue
            await self._send_to(notify_service, message, meta, ctx, nav_url)
            sent.append(recipient_id)
        await self._fire_persistent_notification(type_id, message)
        return sent

    def _child_in_quiet_hours(self, recipient_id: str) -> bool:
        """True if ``recipient_id`` is a child currently inside their quiet-hours
        (do-not-disturb) window. Non-child recipients are never suppressed."""
        if not recipient_id.startswith("child:"):
            return False
        child = self.storage.get_child(recipient_id.split(":", 1)[1])
        if child is None:
            return False
        from homeassistant.util import dt as dt_util

        return _is_within_quiet_hours(child.quiet_hours_start, child.quiet_hours_end, dt_util.now())

    def _resolve_nav_url(self, cfg) -> str:
        """Tap target for this notification: per-type override, else global default."""
        per_type = (getattr(cfg, "nav_url", "") or "").strip()
        if per_type:
            return per_type
        return str(self.storage.get_setting("notification_nav_url", DEFAULT_NOTIFICATION_NAV_URL) or "").strip()

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
            NOTIF_TYPE_BEDTIME_REMINDER: "{child_name}, you still have chores to do before bedtime.",
            NOTIF_TYPE_STREAK_AT_RISK: "{child_name}, complete a chore today to keep your {streak}-day streak!",
            NOTIF_TYPE_ALL_CHORES_DONE: "{child_name} finished every chore today!",
            NOTIF_TYPE_BADGE_EARNED: "{child_name} earned the {badge_name} badge!",
            NOTIF_TYPE_PENDING_CHORE_APPROVAL: "{child_name} completed '{chore_name}' (+{points} {points_name}) — awaiting approval.",
            NOTIF_TYPE_PENDING_REWARD_CLAIM: "{child_name} claimed '{reward_name}' ({cost} {points_name}) — awaiting approval.",
            NOTIF_TYPE_STREAK_MILESTONE: "{child_name} hit a {days}-day streak — +{points} {points_name}!",
            NOTIF_TYPE_LEVEL_UP: "{child_name} reached level {level}! 🎉",
            NOTIF_TYPE_WEEKLY_DIGEST: "TaskMate weekly digest:\n{summary}",
            NOTIF_TYPE_CELEBRATION: "🎉 {message}",
            NOTIF_TYPE_MANDATORY_REMINDER: "{child_name}, you still need to do '{chore_name}'.",
            NOTIF_TYPE_MANDATORY_PARENT_ALERT: "{child_name} still hasn't done the mandatory chore '{chore_name}'.",
            NOTIF_TYPE_MONTHLY_REPORT: "TaskMate {month} report:\n{summary}",
            NOTIF_TYPE_SEASON_CHAMPION: "🏆 {child_name} won the {month} leaderboard with {points} {points_name}!",
            NOTIF_TYPE_FAMILY_GOAL_REACHED: "🎉 Family goal reached: {goal_name}! Time for {goal_reward}.",
        }
        tpl = context.get("message_template") or templates.get(meta.id, "")
        try:
            return tpl.format_map(_SafeDict(context))
        except (ValueError, IndexError, KeyError):
            # Malformed user template (e.g. stray '{') — fall back to raw text
            _LOGGER.warning("Malformed notification template %r, sending raw", tpl)
            return tpl

    async def _send_to(
        self,
        notify_service: str,
        message: str,
        meta: "NotificationTypeMeta",
        context: dict[str, Any],
        nav_url: str = "",
    ) -> None:
        domain, service = notify_service.split(".", 1) if "." in notify_service else ("notify", notify_service)
        if domain != "notify":
            _LOGGER.warning("notify_service must be notify.*, got %s", notify_service)
            return

        data: dict[str, Any] = {"title": "TaskMate", "message": message}

        # Evidence photo (#686): attach it so a parent can approve from the
        # lock screen while actually looking at the tidied room. The URL is
        # pre-signed by the caller, because the companion app fetches
        # attachments without the user's bearer token.
        photo_url = context.get("photo_url") or ""
        attach_photo = bool(photo_url) and service.startswith("mobile_app")

        # Build the mobile-app payload once: the action buttons and the photo
        # are independent, so a completion with no entry id still gets its
        # picture, and a photo-less approval still gets its buttons.
        push: dict[str, Any] = {}
        if meta.actionable:
            entry_id = context.get("entry_id")
            # Tap actions only render on the HA mobile app. Other backends
            # (Telegram, email, SMS, persistent, …) ignore them, so instead of
            # sending dead buttons we append a hint pointing to the panel.
            if service.startswith("mobile_app"):
                if entry_id:
                    # `tag` lets us dismiss this push later (clear_approval) once
                    # the item is reviewed — see _approval_tag.
                    push["tag"] = _approval_tag(entry_id)
                    push["actions"] = [
                        {"action": f"TASKMATE_APPROVE_{entry_id}", "title": "Approve"},
                        {"action": f"TASKMATE_REJECT_{entry_id}", "title": "Reject"},
                    ]
            else:
                data["message"] = f"{message} {_APPROVE_IN_PANEL_HINT}"

        if attach_photo:
            # "image" renders inline on Android; iOS needs it under
            # attachment.url. Sending both keeps one payload working on either.
            push["image"] = photo_url
            push["attachment"] = {"url": photo_url, "content-type": "jpeg"}

        # Tap target (#734): open a chosen place when the notification body is
        # tapped. clickAction=Android, url=iOS — the same value works on both.
        # Only the mobile app honours these; other backends ignore data, so skip.
        if nav_url and service.startswith("mobile_app"):
            push["clickAction"] = nav_url
            push["url"] = nav_url

        if push:
            data["data"] = push

        try:
            await self.hass.services.async_call(domain, service, data, blocking=False)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("notify call failed for %s: %s", notify_service, err)

    async def clear_approval(self, type_id: str, entry_id: str) -> None:
        """Dismiss the mobile push for a reviewed approval (chore or reward).

        The pending-approval push carries a stable ``tag`` (:func:`_approval_tag`).
        Once the item is approved or rejected we send the HA companion app's
        ``clear_notification`` with the same tag so the alert disappears from the
        phone — the fix for the "approve all leaves a pile of notifications"
        problem.

        Gated to ``mobile_app.*`` services only: other backends (Telegram, email,
        persistent) would render the literal "clear_notification" string as a
        message, so they are skipped. Clearing a tag that isn't present is a
        harmless no-op on the app, so no per-recipient bookkeeping is needed.
        """
        if not entry_id:
            return
        cfg = self.storage.get_notification_config(type_id)
        if not cfg.master_enabled:
            return
        tag = _approval_tag(entry_id)
        cleared_services: set[str] = set()
        for recipient_id, route in cfg.routes.items():
            if not route.enabled:
                continue
            notify_service = self._resolve_notify_service(recipient_id)
            if not notify_service:
                continue
            domain, service = notify_service.split(".", 1) if "." in notify_service else ("notify", notify_service)
            if domain != "notify" or not service.startswith("mobile_app"):
                continue
            if service in cleared_services:
                continue
            cleared_services.add(service)
            try:
                await self.hass.services.async_call(
                    "notify",
                    service,
                    {"message": "clear_notification", "data": {"tag": tag}},
                    blocking=False,
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("clear_notification failed for %s: %s", notify_service, err)

    async def _fire_persistent_notification(self, type_id: str, message: str) -> None:
        await self.hass.services.async_call(
            "persistent_notification",
            "create",
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
            entry_id = action[len("TASKMATE_APPROVE_") :]
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
            entry_id = action[len("TASKMATE_REJECT_") :]
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
            self.hass,
            callback,
            hour=hour,
            minute=minute,
            second=0,
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
                try:
                    message = n.message_template.format_map(
                        _SafeDict({"child_name": child_name, "time": n.time}),
                    )
                except (ValueError, IndexError, KeyError):
                    # Malformed user template — send the raw text rather
                    # than silently dropping the notification
                    _LOGGER.warning(
                        "Malformed custom notification template %r, sending raw",
                        n.message_template,
                    )
                    message = n.message_template
                service_name = notify_service.split(".", 1)[1] if "." in notify_service else notify_service
                await self.hass.services.async_call(
                    "notify",
                    service_name,
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

    def ensure_parent_default_routes(self) -> bool:
        """Subscribe enabled parents to default-on parent-audience types.

        A parent-audience type (e.g. pending_chore_approval) is useless without
        a parent route — and adding a parent recipient previously left those
        routes empty, so no one was notified. Fills ONLY types whose routes are
        still empty, so it never overrides routing the user set or cleared.
        Returns True if anything changed (caller is responsible for saving).
        """
        parents = [p for p in self.storage.get_parent_recipients() if p.enabled]
        if not parents:
            return False
        changed = False
        for meta in NOTIFICATION_TYPES:
            if not meta.default_enabled or meta.audience not in ("parent", "both"):
                continue
            if self.storage.get_notification_config(meta.id).routes:
                continue  # already configured — leave it alone
            for p in parents:
                self.storage.set_notification_route(meta.id, p.id, NotificationRoute(enabled=True))
                changed = True
        return changed

    async def upsert_parent(self, p) -> None:
        self.storage.upsert_parent_recipient(p)
        self.ensure_parent_default_routes()
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

    async def set_nav_url(self, type_id: str | None, nav_url: str) -> None:
        """Set the tap target — global (type_id falsy) or per notification type."""
        nav_url = _validate_nav_url(nav_url)
        if type_id:
            if type_id not in NOTIFICATION_TYPES_BY_ID:
                raise ValueError(f"Unknown notification type {type_id}")
            self.storage.set_notification_nav_url(type_id, nav_url)
        else:
            self.storage.set_setting("notification_nav_url", nav_url)
        await self.storage.async_save()

    def _has_outstanding_chores_today(self, child_id: str) -> bool:
        """Returns True if the child has at least one chore assigned today
        that has no approved/pending completion yet."""
        from homeassistant.util import dt as dt_util

        today = dt_util.now().date()
        chores = self.storage.get_chores()
        completions = self.storage.get_completions()
        completed_today = {
            c.chore_id
            for c in completions
            if c.child_id == child_id and dt_util.as_local(c.completed_at).date() == today
        }
        for chore in chores:
            if not chore.assigned_to or child_id not in chore.assigned_to:
                continue
            if chore.id in completed_today:
                continue
            return True
        return False
