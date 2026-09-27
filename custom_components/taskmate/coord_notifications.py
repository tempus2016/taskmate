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

import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change

from . import authz
from .const import (
    DEFAULT_NOTIFICATION_GROUP,
    DEFAULT_NOTIFICATION_NAV_URL,
    NOTIF_TYPE_ALL_CHORES_DONE,
    NOTIF_TYPE_BADGE_EARNED,
    NOTIF_TYPE_BEDTIME_REMINDER,
    NOTIF_TYPE_BIRTHDAY,
    NOTIF_TYPE_BOUNTY_CLAIM_LAPSING,
    NOTIF_TYPE_BOUNTY_POSTED,
    NOTIF_TYPE_CELEBRATION,
    NOTIF_TYPE_FAMILY_GOAL_REACHED,
    NOTIF_TYPE_LEVEL_UP,
    NOTIF_TYPE_MANDATORY_PARENT_ALERT,
    NOTIF_TYPE_MANDATORY_REMINDER,
    NOTIF_TYPE_MONTHLY_REPORT,
    NOTIF_TYPE_PENDING_CHORE_APPROVAL,
    NOTIF_TYPE_PENDING_REWARD_CLAIM,
    NOTIF_TYPE_PRESENCE_ARRIVAL,
    NOTIF_TYPE_RECAP_READY,
    NOTIF_TYPE_SEASON_CHAMPION,
    NOTIF_TYPE_STREAK_AT_RISK,
    NOTIF_TYPE_STREAK_FREEZE_USED,
    NOTIF_TYPE_STREAK_MILESTONE,
    NOTIF_TYPE_WEEKLY_DIGEST,
    NOTIF_TYPE_WISH_PLEDGED,
    NOTIF_TYPE_WISH_REQUESTED,
    QUALITY_RATINGS,
)
from .models import NotificationRoute
from .timewindow import is_within_window, parse_hhmm

_LOGGER = logging.getLogger(__name__)

DEFAULT_MORNING_NOTIFY_TIME = "08:00"

# Appended to actionable notifications sent to non-mobile_app backends, which
# silently ignore tap actions. Gives those recipients a way to act.
_APPROVE_IN_PANEL_HINT = "Open the TaskMate panel to approve or reject."

# Mobile action id prefix for "approve with an N-star quality rating" (#927):
# TASKMATE_RATE_<n>_<completion id>. Distinct from TASKMATE_APPROVE_ so the
# original Approve/Reject ids keep working unchanged when ratings are off.
_RATE_ACTION_PREFIX = "TASKMATE_RATE_"


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
    # Birthday mode (#924): a morning "happy birthday" to the child, at a
    # per-child time (08:00 when none is set).
    NotificationTypeMeta(NOTIF_TYPE_BIRTHDAY, "child", True, True, False, False),
    NotificationTypeMeta(NOTIF_TYPE_STREAK_FREEZE_USED, "both", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_PRESENCE_ARRIVAL, "child", False, False, False, False),
    # Wishlist (#932): a parent hears about a new wish to approve; the child
    # hears when someone pledges towards one of theirs. Off until turned on,
    # like every type added after the first release.
    NotificationTypeMeta(NOTIF_TYPE_WISH_REQUESTED, "parent", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_WISH_PLEDGED, "child", False, False, False, False),
    # Bounty board (#931), both opt-in: a new bounty for the children it's
    # open to (when the parent ticks "notify"), and a warning to the claimer
    # shortly before their claim lapses.
    NotificationTypeMeta(NOTIF_TYPE_BOUNTY_POSTED, "child", False, False, False, False),
    NotificationTypeMeta(NOTIF_TYPE_BOUNTY_CLAIM_LAPSING, "child", False, False, False, False),
    # Recaps (#929): one push per child plus one grouped parent message, sent
    # at the recap send time rather than at midnight when they're built.
    NotificationTypeMeta(NOTIF_TYPE_RECAP_READY, "both", True, False, False, True),
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


def _validate_group(value: str) -> str:
    """Normalise and vet a notification group key.

    The value is an opaque bundling key for the companion app, so anything
    printable will do — but control characters would land inside the JSON
    payload the app parses, and an unbounded string is just storage bloat.
    """
    value = (value or "").strip()
    if not value:
        return ""
    if " " in value:
        raise ValueError("group must not contain spaces (try family-chores)")
    if any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise ValueError("group must not contain control characters")
    if len(value) > 64:
        raise ValueError("group must be 64 characters or fewer")
    return value


# Presence-aware reminders (#926): the child-facing nags that wait for a child
# who is out. Custom reminders are held too (see _make_custom_callback). Good
# news (badges, level-ups, celebrations) is never held — only the nagging.
_PRESENCE_DEFERRED_TYPES = frozenset(
    {
        NOTIF_TYPE_BEDTIME_REMINDER,
        NOTIF_TYPE_STREAK_AT_RISK,
        NOTIF_TYPE_MANDATORY_REMINDER,
    }
)

_PRESENCE_HOME_STATES = ("home", "on", "true", "present")


def _presence_is_home(state: str | None) -> bool | None:
    """Read a presence state: True home, False away, None when it can't tell.

    ``unavailable``/``unknown`` are "can't tell" rather than away, so a flaky
    tracker neither starts an absence nor fakes an arrival.
    """
    if state is None or state in ("unavailable", "unknown", ""):
        return None
    return str(state).lower() in _PRESENCE_HOME_STATES


# Quiet hours reuse the shared time-of-day window helpers (also used by
# time-locked rewards, #857).
_parse_hhmm = parse_hhmm
_is_within_quiet_hours = is_within_window


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
        # Presence-aware reminders (#926). Runtime-only: child_id -> linked
        # entity, when each child left, and who had a reminder held back.
        self._presence_unsub = None
        self._presence_entities: dict[str, str] = {}
        self._presence_away_since: dict[str, datetime] = {}
        self._presence_deferred: set[str] = set()

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
        group = self._resolve_group(cfg)

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
            if type_id in _PRESENCE_DEFERRED_TYPES and self._defer_if_away(recipient_id):
                # The child is out (#926): hold the nag for the arrival nudge
                # instead of buzzing them at the park.
                continue
            await self._send_to(notify_service, message, meta, context, nav_url, group)
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
            "multiplier": "2",
            "count": 3,
            "wish_name": "Lego set",
            "target": 600,
            "pledger": "Grandma",
            "bounty_name": "Wash the car",
            "minutes": 15,
            "period": "January",
            "points_name": self.storage.get_points_name(),
        }
        message = "[TEST] " + self._render_template(meta, ctx)
        cfg = self.storage.get_notification_config(type_id)
        nav_url = self._resolve_nav_url(cfg)
        group = self._resolve_group(cfg)
        sent: list[str] = []
        for recipient_id, route in cfg.routes.items():
            if not route.enabled:
                continue
            notify_service = self._resolve_notify_service(recipient_id)
            if not notify_service:
                continue
            await self._send_to(notify_service, message, meta, ctx, nav_url, group)
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

    def _resolve_group(self, cfg=None) -> str:
        """Group key for this notification: per-type override, else global default.

        Called with no cfg for dispatch paths that have no notification type of
        their own (custom reminders), which always use the global value.
        """
        per_type = (getattr(cfg, "group", "") or "").strip()
        if per_type:
            return per_type
        return str(self.storage.get_setting("notification_group", DEFAULT_NOTIFICATION_GROUP) or "").strip()

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
            NOTIF_TYPE_BIRTHDAY: "🎂 Happy birthday, {child_name}! Every chore pays {multiplier}× today.",
            NOTIF_TYPE_STREAK_FREEZE_USED: "❄️ A streak freeze saved {child_name}'s {streak}-day streak ({freezes_left} left).",
            NOTIF_TYPE_PRESENCE_ARRIVAL: "🏠 You're home, {child_name} — {count} chores left today.",
            NOTIF_TYPE_WISH_REQUESTED: "{child_name} wished for '{wish_name}' ({target} {points_name}) — waiting for your approval.",
            NOTIF_TYPE_WISH_PLEDGED: "💝 {pledger} added {points} {points_name} to your wish '{wish_name}'!",
            NOTIF_TYPE_BOUNTY_POSTED: "🏁 New bounty: {bounty_name} — {points} {points_name}. First to claim it gets it!",
            NOTIF_TYPE_BOUNTY_CLAIM_LAPSING: "⏳ {child_name}, {minutes} minutes left to finish '{bounty_name}' before it goes back on the board.",
            NOTIF_TYPE_RECAP_READY: "✨ Your {period} recap is ready, {child_name}! Tap to watch it.",
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
        group: str = "",
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
                    push["actions"] = self._approval_actions(meta.id, entry_id)
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

        # A caller-supplied tag makes a re-send replace the earlier push on the
        # phone instead of stacking (recaps, #929). Approvals set their own.
        if context.get("tag") and service.startswith("mobile_app"):
            push.setdefault("tag", context["tag"])

        # Grouping (#811): stack TaskMate's notifications into one bundle so
        # they don't scatter through the phone's other HA alerts. Android reads
        # data.group; iOS threads on push.thread-id, so send both — same value,
        # and each platform ignores the other's key.
        if group and service.startswith("mobile_app"):
            push["group"] = group
            push["push"] = {"thread-id": group}

        if push:
            data["data"] = push

        try:
            await self.hass.services.async_call(domain, service, data, blocking=False)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("notify call failed for %s: %s", notify_service, err)

    def _approval_actions(self, type_id: str, entry_id: str) -> list[dict[str, str]]:
        """Mobile action buttons for a pending-approval push.

        With quality ratings on (#927) a chore approval offers the three star
        ratings instead of a plain Approve, so a parent can rate from the lock
        screen. Reject goes last: Android shows at most three actions, so the
        ratings take priority there and Reject stays in the panel/card. With
        the feature off — and always for reward claims — the push keeps the
        original Approve/Reject ids, so older pushes still in flight resolve.
        """
        coordinator = getattr(self, "coordinator", None)
        rated = (
            type_id == NOTIF_TYPE_PENDING_CHORE_APPROVAL
            and coordinator is not None
            and coordinator.quality_rating_enabled()
        )
        if rated:
            return [
                *({"action": f"{_RATE_ACTION_PREFIX}{n}_{entry_id}", "title": "★" * n} for n in QUALITY_RATINGS),
                {"action": f"TASKMATE_REJECT_{entry_id}", "title": "Reject"},
            ]
        return [
            {"action": f"TASKMATE_APPROVE_{entry_id}", "title": "Approve"},
            {"action": f"TASKMATE_REJECT_{entry_id}", "title": "Reject"},
        ]

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
        # Approving/rejecting is a parent action. The event bus is a second door
        # into it, so enforce the same admin/parent identity check the service
        # and WebSocket approval paths use — otherwise anyone who can fire this
        # event (e.g. a child's Companion-app registration) could self-approve.
        if not await authz.async_context_is_parent(self.hass, coordinator, getattr(event, "context", None)):
            _LOGGER.warning("Ignoring TaskMate mobile action from a non-parent user")
            return

        if action.startswith(_RATE_ACTION_PREFIX):
            # TASKMATE_RATE_<n>_<completion id> (#927): approve with a rating.
            stars, _, entry_id = action[len(_RATE_ACTION_PREFIX) :].partition("_")
            try:
                rating = int(stars)
            except ValueError:
                _LOGGER.info("Mobile action %s — malformed rating", action)
                return

            async def _approve_rated(completion_id: str) -> None:
                await coordinator.async_approve_chore(completion_id, rating=rating)

            await self._review_from_mobile(action, entry_id, _approve_rated, coordinator.async_approve_reward)
        elif action.startswith("TASKMATE_APPROVE_"):
            await self._review_from_mobile(
                action,
                action[len("TASKMATE_APPROVE_") :],
                coordinator.async_approve_chore,
                coordinator.async_approve_reward,
            )
        elif action.startswith("TASKMATE_REJECT_"):
            await self._review_from_mobile(
                action,
                action[len("TASKMATE_REJECT_") :],
                coordinator.async_reject_chore,
                coordinator.async_reject_reward,
            )

    async def _review_from_mobile(self, action: str, entry_id: str, review_chore, review_reward) -> None:
        """Send a mobile review to whichever record the id belongs to.

        A chore completion id and a reward claim id look alike, so this used to
        try the chore path and fall back to the reward path when it raised. It
        never does: approving or rejecting an unknown completion is a no-op,
        not an error, so the fallback was unreachable and every reward push
        button did nothing at all. The id itself decides.
        """
        if any(c.id == entry_id for c in self.storage.get_completions()):
            review = review_chore
        elif any(c.id == entry_id for c in self.storage.get_reward_claims()):
            review = review_reward
        else:
            _LOGGER.info("Mobile action %s — entry not found", action)
            return
        try:
            await review(entry_id)
        except (ValueError, KeyError) as err:
            # A stale push: the item was reviewed elsewhere, or the reward has
            # since sold out. Nothing to do, but say why in the log.
            _LOGGER.info("Mobile action %s could not be applied: %s", action, err)

    async def send_recap_ready(
        self,
        per_child: list[dict[str, Any]],
        parent_message: str,
        *,
        to_children: bool = True,
        to_parents: bool = True,
    ) -> list[str]:
        """Announce new recaps (#929): one push per child, one grouped for parents.

        Goes around ``fire()`` because a single dispatch here is several
        messages with different text. The routing rules are the same: the
        master switch, each recipient's route, child quiet hours and the parent
        routing policy. One ``taskmate_recap_ready`` event fires per child even
        when the notification is switched off, like every other type.
        """
        meta = NOTIFICATION_TYPES_BY_ID[NOTIF_TYPE_RECAP_READY]
        cfg = self.storage.get_notification_config(NOTIF_TYPE_RECAP_READY)
        nav_url = self._resolve_nav_url(cfg)
        group = self._resolve_group(cfg)
        sent: list[str] = []
        for item in per_child:
            rid = f"child:{item['child_id']}"
            fired: list[str] = []
            route = cfg.routes.get(rid)
            if (
                cfg.master_enabled
                and to_children
                and route is not None
                and route.enabled
                and not self._child_in_quiet_hours(rid)
            ):
                notify_service = self._resolve_notify_service(rid)
                if notify_service:
                    ctx = {**item, "tag": f"taskmate_recap_{item['child_id']}"}
                    await self._send_to(notify_service, item["message"], meta, ctx, nav_url, group)
                    fired.append(rid)
            sent.extend(fired)
            self._fire_bus_event(
                NOTIF_TYPE_RECAP_READY,
                {
                    "child_id": item["child_id"],
                    "child_name": item["child_name"],
                    "count": len(item.get("recaps", [])),
                    "recaps": item.get("recaps", []),
                },
                fired,
            )
        if cfg.master_enabled and to_parents and per_child:
            for rid in sorted(self._route_parents(NOTIF_TYPE_RECAP_READY, cfg, None)):
                notify_service = self._resolve_notify_service(rid)
                if not notify_service:
                    continue
                ctx = {"tag": "taskmate_recaps"}
                await self._send_to(notify_service, parent_message, meta, ctx, nav_url, group)
                sent.append(rid)
        return sent

    # ------------------------------------------------------------------
    # Scheduler — time-gated callbacks
    # ------------------------------------------------------------------

    def cancel_schedules(self) -> None:
        """Cancel all registered time triggers (idempotent; also used on unload)."""
        for unsub in self._scheduled_unsubs:
            with contextlib.suppress(Exception):
                unsub()
        self._scheduled_unsubs = []

    async def async_setup_schedules(self) -> None:
        """Cancel any existing time callbacks and register fresh ones from current config.

        Call this on startup AND after any config change that affects schedules
        (e.g. bedtime time edited, custom notification time edited, master toggled).
        """
        self.cancel_schedules()

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

        # Birthday (#924) — per-child morning time, only fires on the day
        cfg = self.storage.get_notification_config("birthday")
        if cfg.master_enabled:
            for recipient_id, route in cfg.routes.items():
                if not route.enabled or not recipient_id.startswith("child:"):
                    continue
                self._register_at(
                    route.time or DEFAULT_MORNING_NOTIFY_TIME,
                    self._make_birthday_callback(recipient_id.split(":", 1)[1]),
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

    def _make_birthday_callback(self, child_id: str):
        async def _cb(now):
            coord = self.coordinator
            child = self.storage.get_child(child_id)
            if child is None or coord is None or not coord.is_birthday(child):
                return
            await self.fire(
                "birthday",
                {
                    "child_name": child.name,
                    "child_id": child_id,
                    "multiplier": f"{coord.birthday_multiplier():g}",
                },
                only_recipients={f"child:{child_id}"},
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
            # A birthday day off can't break the streak, so don't nag (#924).
            if self.coordinator is not None and self.coordinator.is_birthday_day_off(child) is True:
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
                if self._defer_if_away(recipient_id):
                    continue  # held for the arrival nudge (#926)
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
                payload: dict[str, Any] = {"title": "TaskMate", "message": message}
                # Custom reminders bypass _send_to, so apply the group here too
                # (#811) — otherwise they'd be the one kind of TaskMate alert
                # that still lands outside the bundle.
                group = self._resolve_group()
                if group and service_name.startswith("mobile_app"):
                    payload["data"] = {"group": group, "push": {"thread-id": group}}
                await self.hass.services.async_call(
                    "notify",
                    service_name,
                    payload,
                    blocking=False,
                )
            self.hass.bus.async_fire(
                "taskmate_custom_notification",
                {"id": n.id, "name": n.name, "recipients": n.recipient_ids},
            )

        return _cb

    # ------------------------------------------------------------------
    # Presence-aware reminders (#926)
    # ------------------------------------------------------------------

    def child_is_away(self, child_id: str) -> bool:
        """True only when the child's presence entity positively says "not home".

        No entity, a missing entity, or an unavailable/unknown one all read as
        home: a broken tracker must not silence every reminder.
        """
        entity_id = self._presence_entities.get(child_id)
        if entity_id is None:
            child = self.storage.get_child(child_id)
            entity_id = (getattr(child, "presence_entity", "") or "").strip() if child else ""
        if not entity_id:
            return False
        state = self.hass.states.get(entity_id)
        return _presence_is_home(getattr(state, "state", None)) is False

    def _defer_if_away(self, recipient_id: str) -> bool:
        """Hold a reminder for an away child; True means "don't send it now"."""
        if not recipient_id.startswith("child:"):
            return False
        child_id = recipient_id.split(":", 1)[1]
        if not self.child_is_away(child_id):
            return False
        self._presence_deferred.add(child_id)
        return True

    def sync_presence_tracking(self) -> None:
        """(Re)subscribe to the children's presence entities if they changed.

        Cheap enough to call on every coordinator refresh: it compares the
        child -> entity map and only resubscribes on a difference, so adding,
        editing, removing or importing a child all pick it up.
        """
        wanted: dict[str, str] = {}
        for child in self.storage.get_children():
            entity_id = (getattr(child, "presence_entity", "") or "").strip()
            if entity_id:
                wanted[child.id] = entity_id
        if wanted == self._presence_entities and (self._presence_unsub is not None or not wanted):
            return

        self.cancel_presence_tracking()
        # A child whose entity changed (or was removed) starts from scratch —
        # an absence measured on the old tracker says nothing about the new one.
        for child_id in list(self._presence_away_since):
            if wanted.get(child_id) != self._presence_entities.get(child_id):
                self._presence_away_since.pop(child_id, None)
        self._presence_deferred &= set(wanted)
        self._presence_entities = wanted
        if not wanted:
            return

        from homeassistant.util import dt as dt_util

        # Seed absences already under way (e.g. across a restart) from the
        # entity's own last_changed, so the min-away rule still holds.
        for child_id, entity_id in wanted.items():
            if child_id in self._presence_away_since:
                continue
            state = self.hass.states.get(entity_id)
            if _presence_is_home(getattr(state, "state", None)) is False:
                since = getattr(state, "last_changed", None)
                self._presence_away_since[child_id] = since if isinstance(since, datetime) else dt_util.now()

        self._presence_unsub = async_track_state_change_event(
            self.hass,
            sorted(set(wanted.values())),
            self._presence_state_changed,
        )

    def cancel_presence_tracking(self) -> None:
        """Drop the presence subscription (idempotent; also used on unload)."""
        if self._presence_unsub is not None:
            with contextlib.suppress(Exception):
                self._presence_unsub()
            self._presence_unsub = None

    @callback
    def _presence_state_changed(self, event) -> None:
        data = getattr(event, "data", None) or {}
        entity_id = data.get("entity_id")
        new_state = data.get("new_state")
        is_home = _presence_is_home(getattr(new_state, "state", None))
        if is_home is None:
            return  # flaky tracker: keep whatever we last knew

        from homeassistant.util import dt as dt_util

        now = dt_util.now()
        for child_id, tracked in self._presence_entities.items():
            if tracked != entity_id:
                continue
            if not is_home:
                # Moving between zones (school -> park) is one absence.
                self._presence_away_since.setdefault(child_id, now)
                continue
            # Consume the absence here, synchronously, so a burst of "home"
            # updates (GPS jitter) can only ever produce one nudge.
            away_since = self._presence_away_since.pop(child_id, None)
            deferred = child_id in self._presence_deferred
            self._presence_deferred.discard(child_id)
            if away_since is None and not deferred:
                continue
            self.hass.async_create_task(self.async_arrival_nudge(child_id, away_since, deferred, now))

    async def async_arrival_nudge(
        self,
        child_id: str,
        away_since: datetime | None,
        deferred: bool,
        now: datetime,
    ) -> bool:
        """Send one "you're home — N chores left" nudge. Returns True if fired.

        Fires when the child was out for at least the configured minimum, or
        when a reminder was held back while they were out (however short the
        trip — held reminders are deferred, never dropped). Held reminders
        collapse into this single nudge rather than replaying one by one.
        Quiet hours still apply, via ``fire()``.
        """
        child = self.storage.get_child(child_id)
        if child is None:
            return False
        if not deferred:
            min_away = timedelta(minutes=self.storage.get_presence_arrival_min_away())
            if away_since is None or now - away_since < min_away:
                return False
        count = self._outstanding_chore_count(child_id)
        if count <= 0:
            return False
        await self.fire(
            NOTIF_TYPE_PRESENCE_ARRIVAL,
            {"child_name": child.name, "child_id": child_id, "count": count},
            only_recipients={f"child:{child_id}"},
        )
        return True

    def _outstanding_chore_count(self, child_id: str) -> int:
        """How many chores the child still owes today (what their card shows)."""
        coordinator = getattr(self, "coordinator", None)
        due = getattr(coordinator, "get_due_chores_for_child", None) if coordinator else None
        if callable(due):
            try:
                return len(due(child_id))
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Due-chore lookup failed for %s", child_id, exc_info=True)
        return 1 if self._has_outstanding_chores_today(child_id) else 0

    async def set_presence_arrival_min_away(self, minutes: int) -> None:
        self.storage.set_presence_arrival_min_away(minutes)
        await self.storage.async_save()

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

    async def set_group(self, type_id: str | None, group: str) -> None:
        """Set the group key — global (type_id falsy) or per notification type."""
        group = _validate_group(group)
        if type_id:
            if type_id not in NOTIFICATION_TYPES_BY_ID:
                raise ValueError(f"Unknown notification type {type_id}")
            self.storage.set_notification_group(type_id, group)
        else:
            self.storage.set_setting("notification_group", group)
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
        # Birthday day off (#924): only mandatory chores are still owed.
        coord = self.coordinator
        birthday_off = coord is not None and coord.is_birthday_day_off(self.storage.get_child(child_id)) is True
        for chore in chores:
            if not chore.assigned_to or child_id not in chore.assigned_to:
                continue
            if chore.id in completed_today:
                continue
            if birthday_off and not getattr(chore, "mandatory", False):
                continue
            return True
        return False
