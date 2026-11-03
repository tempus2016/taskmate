"""Kid onboarding tour: a first-run walkthrough on the Child card and Kiosk.

The tour itself lives in the cards (www/taskmate-tour.js). The backend keeps
one small record per child — when they finished it, or at which step they
skipped it — so the tour follows a child from the kitchen tablet to their own
phone instead of replaying on every new screen.

Settings:

* ``tour_enabled`` (default on) — show the tour at all.
* ``tour_auto_read`` (default on) — pre-reader cards speak each step through
  the read-aloud speaker without a tap.

A child may only mark their own tour (the linked-child rule every child action
uses); resetting it is a grown-up's job.

Reading a step aloud goes through the existing read-aloud path
(``async_read_aloud``) with words built here from the locale catalogue, never
from the caller: like ``taskmate.read_aloud``, a child account must not be able
to make the speaker say anything it likes.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from homeassistant.util import dt as dt_util

from . import notify_strings

_LOGGER = logging.getLogger(__name__)

TOUR_SECTION = "kid_tour"
TOUR_MIGRATED_FLAG = "_kid_tour_migrated"

# Step keys, in tour order. The cards pick which of these to show.
TOUR_STEPS = ("hello", "tick", "points", "streak", "rewards")
PRE_READER_STEPS = ("pre_tick", "pre_points", "pre_rewards")
TOUR_SPEAKABLE = (*TOUR_STEPS, *PRE_READER_STEPS)
TOUR_MAX_STEP = len(TOUR_STEPS)

# One spoken step per child every couple of seconds is plenty: a speaker
# button hammered by a four-year-old shouldn't queue a minute of speech.
SPEAK_MIN_INTERVAL = 2.0

_LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z]{2,4})?$")


def _bool_setting(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "on", "yes")


class KidTourMixin:
    """Per-child onboarding-tour state."""

    def tour_enabled(self) -> bool:
        return _bool_setting(self.storage.get_setting("tour_enabled", True), True)

    def tour_auto_read(self) -> bool:
        return _bool_setting(self.storage.get_setting("tour_auto_read", True), True)

    def _tour_states(self) -> dict[str, dict[str, Any]]:
        return self.storage.get_section(TOUR_SECTION, dict)

    def tour_state(self, child_id: str) -> dict[str, Any]:
        """``{"done": "YYYY-MM-DD"}``, ``{"skipped": N, "on": date}`` or ``{}``."""
        state = self._tour_states().get(child_id)
        return dict(state) if isinstance(state, dict) else {}

    def tour_done(self, child_id: str) -> bool:
        """Finished or skipped: either way the card shouldn't start it again."""
        state = self.tour_state(child_id)
        return bool(state.get("done") or state.get("skipped"))

    def tour_card_settings(self) -> dict[str, int] | None:
        """The overview's tour switches, or None while the tour is off.

        ``speak`` means a read-aloud speaker is set up, so the speaker button
        has somewhere to talk; ``auto`` is the pre-reader auto-read switch.
        """
        if not self.tour_enabled():
            return None
        out: dict[str, int] = {}
        if self._tour_can_speak():
            out["speak"] = 1
            if self.tour_auto_read():
                out["auto"] = 1
        return out

    def _tour_can_speak(self) -> bool:
        if not self._tts_setting("read_aloud_media_player", ""):
            return False
        try:
            return bool(self._resolve_tts_entity())
        except Exception:  # noqa: BLE001 - a hidden speaker button beats a broken sensor
            return False

    def tour_status_all(self) -> dict[str, dict[str, Any]]:
        """Every non-adult child's tour record, for the panel's Settings table."""
        states = self._tour_states()
        out: dict[str, dict[str, Any]] = {}
        for child in self.storage.get_children():
            if getattr(child, "is_adult", False):
                continue
            state = states.get(child.id)
            if isinstance(state, dict) and state:
                out[child.id] = dict(state)
        return out

    def _tour_child(self, child_id: str):
        child = self.storage.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        if getattr(child, "is_adult", False):
            raise ValueError("Grown-up profiles don't get the tour")
        return child

    async def async_tour_mark(self, child_id: str, status: str, step: int = 0) -> dict[str, Any]:
        """Record that a child finished the tour, or skipped it at ``step``.

        The first answer sticks: a second device finishing a tour the child
        already skipped elsewhere doesn't rewrite it. Only a reset clears it.
        """
        self._tour_child(child_id)
        if status not in ("done", "skipped"):
            raise ValueError("status must be 'done' or 'skipped'")
        states = self._tour_states()
        existing = states.get(child_id)
        if isinstance(existing, dict) and (existing.get("done") or existing.get("skipped")):
            return dict(existing)
        today = dt_util.as_local(dt_util.now()).date().isoformat()
        if status == "done":
            record: dict[str, Any] = {"done": today}
        else:
            record = {"skipped": max(1, min(TOUR_MAX_STEP, int(step or 1))), "on": today}
        states[child_id] = record
        await self.storage.async_save()
        await self.async_refresh()
        return dict(record)

    async def async_tour_reset(self, child_id: str) -> None:
        """Show the tour again: forget the child's record."""
        self._tour_child(child_id)
        if self._tour_states().pop(child_id, None) is None:
            return
        await self.storage.async_save()
        await self.async_refresh()

    def build_tour_message(self, child_id: str, step: str, language: str | None = None) -> str:
        """The words for one tour step, from the locale catalogue."""
        child = self._tour_child(child_id)
        if step not in TOUR_SPEAKABLE:
            raise ValueError(f"Unknown tour step {step}")
        points_name = self.storage.data.get("points_name") or "Stars"
        params = {"name": child.name, "points_name": points_name}
        title = notify_strings.render(self.hass, f"tour_{step}_title", params, language)
        body = notify_strings.render(self.hass, f"tour_{step}_body", params, language)
        return " ".join(part for part in (title.strip(), body.strip()) if part)

    async def async_tour_speak(
        self,
        child_id: str,
        step: str,
        language: str = "",
        context: Any = None,
    ) -> str:
        """Speak one tour step on the read-aloud speaker. Returns what was said."""
        lang = language if language and _LANG_RE.match(language) else None
        if lang:
            await notify_strings.async_load(self.hass, lang)
        message = self.build_tour_message(child_id, step, lang)
        last = getattr(self, "_tour_last_spoken", None)
        if last is None:
            last = {}
            self._tour_last_spoken = last
        now = time.monotonic()
        if now - last.get(child_id, -SPEAK_MIN_INTERVAL) < SPEAK_MIN_INTERVAL:
            raise ValueError("Already speaking; try again in a moment")
        last[child_id] = now
        return await self.async_read_aloud(child_id=child_id, message=message, context=context)
