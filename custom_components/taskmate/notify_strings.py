"""Localised text for TaskMate's push notifications (#1037).

The wording lives in the card/panel catalogue (``www/locales/<lang>.json``)
under ``notify.*`` keys, so translators keep one file per language. English is
also baked in here: it is the fallback for a missing locale, a missing key, or
a translation whose placeholders don't format, so a notification always goes
out with something readable.

Usage: ``await async_load(hass)`` once before building text (it reads the
locale file off the event loop and caches it), then ``render(hass, key, ...)``
synchronously with a dict of placeholders. Without a load — or on a hass with no language — render falls
back to English.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)

_PREFIX = "notify."
_LOCALES_DIR = Path(__file__).parent / "www" / "locales"

# English source text, keyed without the ``notify.`` prefix. en.json carries
# the same strings (a test keeps the two in step).
DEFAULTS: dict[str, str] = {
    "bedtime_reminder": "{child_name}, you still have chores to do before bedtime.",
    "streak_at_risk": "{child_name}, complete a chore today to keep your {streak}-day streak!",
    "all_chores_done": "{child_name} finished every chore today!",
    "badge_earned": "{child_name} earned the {badge_name} badge!",
    "pending_chore_approval": "{child_name} completed '{chore_name}' (+{points} {points_name}) — awaiting approval.",
    "pending_reward_claim": "{child_name} claimed '{reward_name}' ({cost} {points_name}) — awaiting approval.",
    "streak_milestone": "{child_name} hit a {days}-day streak — +{points} {points_name}!",
    "level_up": "{child_name} reached level {level}! 🎉",
    "weekly_digest": "TaskMate weekly digest:\n{summary}",
    "celebration": "🎉 {message}",
    "mandatory_reminder": "{child_name}, you still need to do '{chore_name}'.",
    "mandatory_parent_alert": "{child_name} still hasn't done the mandatory chore '{chore_name}'.",
    "monthly_report": "TaskMate {month} report:\n{summary}",
    "season_champion": "🏆 {child_name} won the {month} leaderboard with {points} {points_name}!",
    "family_goal_reached": "🎉 Family goal reached: {goal_name}! Time for {goal_reward}.",
    "birthday": "🎂 Happy birthday, {child_name}! Every chore pays {multiplier}× today.",
    "streak_freeze_used": "❄️ A streak freeze saved {child_name}'s {streak}-day streak ({freezes_left} left).",
    "presence_arrival": "🏠 You're home, {child_name} — {count} chores left today.",
    "wish_requested": "{child_name} wished for '{wish_name}' ({target} {points_name}) — waiting for your approval.",
    "wish_pledged": "💝 {pledger} added {points} {points_name} to your wish '{wish_name}'!",
    "bounty_posted": "🏁 New bounty: {bounty_name} — {points} {points_name}. First to claim it gets it!",
    "bounty_claim_lapsing": (
        "⏳ {child_name}, {minutes} minutes left to finish '{bounty_name}' before it goes back on the board."
    ),
    "recap_ready": "✨ Your {period} recap is ready, {child_name}! Tap to watch it.",
    "item_rejected": "↩️ {child_name}, '{item_name}' was sent back{reason_text}",
    "auction_opened": "🔨 New auction: {chore_name} on {date}, up to {max_points} {points_name}. Lowest bid wins!",
    "auction_closing": "⏳ {child_name}, bidding on '{chore_name}' closes in {minutes} minutes.",
    "auction_result": "🔨 Auction closed: {result_text}",
    "inspection_started": (
        "🔍 {child_name}, a grown-up is coming to inspect '{chore_name}' before {until}. "
        "Keep it looking great for +{bonus} {points_name}!"
    ),
    "inspection_passed": (
        "🌟 Inspection passed, {child_name}! '{chore_name}' looked great: +{bonus} {points_name}{note_text}"
    ),
    "inspection_reminder": (
        "🔍 {child_name}'s '{chore_name}' inspection closes in {minutes} minutes — pass or fail it before {until}."
    ),
    # Pieces that callers assemble into the messages above.
    "auction_won": "{child_name} won '{chore_name}' on {date} for {points} {points_name}.",
    "auction_no_bids": "no bids for '{chore_name}', so it goes back to the normal rota.",
    "auction_called_off": "the auction for '{chore_name}' was called off. It goes back to the normal rota.",
    "weekly_digest_line": "• {child_name}: {chores} chores, {points} {points_name} earned",
    "monthly_report_line": "• {child_name}: {chores} chores, {points} {points_name}, level {level}, best streak {streak}",
    # Celebration messages (the celebration push and the taskmate_celebration
    # event), keyed celebrate_<kind>.
    "celebrate_all_chores_done": "{child_name} finished every chore today!",
    "celebrate_birthday": "Happy birthday, {child_name}!",
    "celebrate_challenge_completed": "{child_name} completed the challenge '{challenge_name}'!",
    "celebrate_inspection_passed": "{child_name}'s {chore_name} passed inspection!",
    "celebrate_level_up": "{child_name} reached level {level}!",
    "celebrate_perfect_week": "{child_name} earned a perfect week — +{bonus}!",
    "celebrate_quest_completed": "{child_name} completed the quest '{quest_name}'!",
    "celebrate_streak_milestone": "{child_name} hit a {days}-day streak!",
    # Recap announcements: the single-recap child push is recap_ready above.
    "recap_ready_many": "✨ {count} new recaps are ready, {child_name}! Tap to watch them.",
    "recap_parent_one": "✨ New {period} recaps are ready for {names}. Tap to see them.",
    "recap_parent_many": "✨ New recaps are ready for {names}. Tap to see them.",
    "period_weekly": "weekly",
    "period_range": "{start}–{end}",
    # Lists, dates and month names used inside messages.
    "names_and": "{names} and {last}",
    "month_year": "{month} {year}",
    "short_date": "{weekday} {day} {month}",
    **{
        f"month_{i}": name
        for i, name in enumerate(
            (
                "January",
                "February",
                "March",
                "April",
                "May",
                "June",
                "July",
                "August",
                "September",
                "October",
                "November",
                "December",
            ),
            1,
        )
    },
    **{
        f"month_short_{i}": name
        for i, name in enumerate(
            ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1
        )
    },
    # ISO weekday numbers: 1 = Monday.
    **{f"weekday_short_{i}": name for i, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"), 1)},
    # Stand-in names for a test push from the panel.
    "sample_chore": "Tidy room",
    "sample_reward": "Movie night",
    "sample_badge": "Star Helper",
    "sample_goal": "Movie night fund",
    "sample_goal_reward": "a family movie night",
    "sample_wish": "Lego set",
    "sample_pledger": "Grandma",
    "sample_bounty": "Wash the car",
    "sample_reason": "Not finished",
    "sample_note": "Brilliant job!",
    # Approval push buttons and the hint for backends that can't show them.
    "action_approve": "Approve",
    "action_reject": "Reject",
    "action_reject_placeholder": "Reason (optional)",
    "approve_in_panel_hint": "Open the TaskMate panel to approve or reject.",
}

_EVENT_CORE_CONFIG_UPDATE = "core_config_updated"

# language -> merged strings (DEFAULTS overlaid with the locale's own).
_cache: dict[str, dict[str, str]] = {}


class SafeDict(dict):
    """str.format_map dict that leaves missing keys as `{key}` literal."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _language(hass: Any) -> str:
    config = getattr(hass, "config", None)
    lang = getattr(config, "language", None)
    return lang if isinstance(lang, str) and lang else "en"


def _read_locale(lang: str) -> dict[str, str]:
    """English, overlaid with the base language (pt for pt-BR), then the exact one."""
    strings = dict(DEFAULTS)
    candidates = [lang.split("-", 1)[0], lang] if "-" in lang else [lang]
    for code in candidates:
        path = _LOCALES_DIR / f"{code}.json"
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _LOGGER.warning("Could not read TaskMate locale %s for notifications", path.name)
            continue
        for key, value in data.items():
            if key.startswith(_PREFIX) and isinstance(value, str) and value.strip():
                strings[key[len(_PREFIX) :]] = value
    return strings


async def async_load(hass: Any) -> None:
    """Cache the notification strings for HA's current language."""
    lang = _language(hass)
    if lang in _cache:
        return
    run: Any = getattr(hass, "async_add_executor_job", None)
    if not callable(run):
        return
    try:
        _cache[lang] = await run(_read_locale, lang)
    except Exception:  # noqa: BLE001 - wording is cosmetic; never block a notification
        _LOGGER.debug("Could not load TaskMate notification strings for %s", lang, exc_info=True)


def text(hass: Any, key: str) -> str:
    """The raw template for ``key`` in HA's language (English if not loaded)."""
    return _cache.get(_language(hass), DEFAULTS).get(key) or DEFAULTS.get(key, "")


def render(hass: Any, key: str, params: Mapping[str, Any]) -> str:
    """Format ``key`` with ``params``; a broken translation falls back to English."""
    tpl = text(hass, key)
    try:
        return tpl.format_map(SafeDict(params))
    except (ValueError, IndexError, KeyError, AttributeError):
        _LOGGER.warning("Malformed TaskMate notification text for %s, using English", key)
        return DEFAULTS.get(key, "").format_map(SafeDict(params))


def async_watch_language(hass: Any):
    """Reload the strings when HA's language changes; returns the unsubscribe."""

    def _changed(_event) -> None:
        hass.async_create_task(async_load(hass))

    return hass.bus.async_listen(_EVENT_CORE_CONFIG_UPDATE, _changed)


def month_name(hass: Any, month: int) -> str:
    return text(hass, f"month_{month}")


def month_year(hass: Any, day: date) -> str:
    """Month and year, like "September 2026", in HA's language."""
    return render(hass, "month_year", {"month": month_name(hass, day.month), "year": day.year})


def short_date(hass: Any, day: date) -> str:
    """A short date, like "Sat 4 Oct", in HA's language."""
    return render(
        hass,
        "short_date",
        {
            "weekday": text(hass, f"weekday_short_{day.isoweekday()}"),
            "day": day.day,
            "month": text(hass, f"month_short_{day.month}"),
        },
    )


def join_names(hass: Any, names: list[str]) -> str:
    """A list of names, like "Malia, Vaiha and Alex", in HA's language."""
    if len(names) <= 1:
        return names[0] if names else ""
    return render(hass, "names_and", {"names": ", ".join(names[:-1]), "last": names[-1]})
