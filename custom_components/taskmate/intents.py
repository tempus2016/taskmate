"""Home Assistant conversation intents for TaskMate (FEAT-12).

Registers intent handlers so a voice/text assistant can answer and act:

* "how many chores does Malia have left?"       → TaskMateChoresLeft
* "how many stars does Alex have?"              → TaskMatePoints
* "mark make bed as done for Malia"             → TaskMateCompleteChore
* "what's Malia's next job?"                    → TaskMateNextChore
* "how close is Alex to the cinema trip?"       → TaskMateRewardProgress

The default conversation agent matches *sentences* to these intent names; ship
the example sentences in ``custom_sentences/<lang>/taskmate.yaml`` into your HA
config (see custom_sentences/README.md). Replies are spoken in Home Assistant's
language from the same catalogue as the push notifications (``notify.voice_*``
keys). The speech-building logic is kept in pure helpers so it is unit-testable
without the conversation stack.

Completing by voice is the child's own completion, never a parent's: approval
rules apply exactly as if they had tapped Done, and the linked-child rule
decides whether the speaker may act for that child.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent

from . import notify_strings
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

INTENT_CHORES_LEFT = "TaskMateChoresLeft"
INTENT_POINTS = "TaskMatePoints"
INTENT_COMPLETE_CHORE = "TaskMateCompleteChore"
INTENT_NEXT_CHORE = "TaskMateNextChore"
INTENT_REWARD_PROGRESS = "TaskMateRewardProgress"


def _get_coordinator(hass: HomeAssistant):
    from .coordinator import TaskMateCoordinator

    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, TaskMateCoordinator):
            return value
    return None


# The language the question was asked in, so a German question gets a German
# answer whatever Home Assistant's own language is. Unset: HA's language.
_reply_language: ContextVar[str | None] = ContextVar("taskmate_reply_language", default=None)


def _say(coordinator, key: str, **params: Any) -> str:
    return notify_strings.render(getattr(coordinator, "hass", None), f"voice_{key}", params, _reply_language.get())


async def _prepare_reply(intent_obj) -> None:
    language = getattr(intent_obj, "language", None)
    language = language if isinstance(language, str) and language else None
    _reply_language.set(language)
    await notify_strings.async_load(intent_obj.hass, language)


def _norm(text: str) -> str:
    return " ".join(str(text or "").lower().replace("'", "").replace("’", "").split())


def _find_child(coordinator, name: str):
    """Case-insensitive child lookup by name."""
    if coordinator is None or not name:
        return None
    target = name.strip().lower()
    for child in coordinator.storage.get_children():
        if child.name.strip().lower() == target:
            return child
    return None


def _best_match(items, said: str, key=lambda x: x.name):
    """The item whose name best matches what was said: exact, then contains, then word overlap."""
    target = _norm(said)
    if not target:
        return None
    names = [(item, _norm(key(item))) for item in items]
    for item, name in names:
        if name == target:
            return item
    for item, name in names:
        if target in name or name in target:
            return item
    words = set(target.split())
    scored = [(len(words & set(name.split())), item) for item, name in names]
    scored = [s for s in scored if s[0] > 0]
    return max(scored, key=lambda s: s[0])[1] if scored else None


def chores_left_speech(coordinator, name: str) -> str:
    """Speech for 'how many chores does <name> have left'."""
    child = _find_child(coordinator, name)
    if child is None:
        return _say(coordinator, "not_found", name=name)
    count = len(coordinator.get_due_chores_for_child(child.id))
    if count == 0:
        return _say(coordinator, "chores_left_none", child_name=child.name)
    if count == 1:
        return _say(coordinator, "chores_left_one", child_name=child.name)
    return _say(coordinator, "chores_left_many", child_name=child.name, count=count)


def points_speech(coordinator, name: str) -> str:
    """Speech for 'how many points does <name> have'."""
    child = _find_child(coordinator, name)
    if child is None:
        return _say(coordinator, "not_found", name=name)
    points_name = coordinator.storage.get_points_name()
    return _say(coordinator, "points", child_name=child.name, points=child.points, points_name=points_name)


def next_chore_speech(coordinator, name: str) -> str:
    """Speech for "what's <name>'s next job"."""
    from .watch import next_chore_for_child

    child = _find_child(coordinator, name)
    if child is None:
        return _say(coordinator, "not_found", name=name)
    chore = next_chore_for_child(coordinator, child.id)
    if chore is None:
        due = coordinator.get_due_chores_for_child(child.id)
        chore = due[0] if due else None
    if chore is None:
        return _say(coordinator, "chores_left_none", child_name=child.name)
    return _say(coordinator, "next", child_name=child.name, chore_name=chore.name)


def reward_progress_speech(coordinator, name: str, reward_said: str = "") -> str:
    """Speech for "how close is <name> to <reward>" (the nearest one when none is named)."""
    child = _find_child(coordinator, name)
    if child is None:
        return _say(coordinator, "not_found", name=name)
    rewards = [
        r
        for r in coordinator.storage.get_rewards()
        if (not r.assigned_to or child.id in r.assigned_to) and int(r.cost or 0) > 0
    ]
    if not rewards:
        return _say(coordinator, "no_rewards", child_name=child.name)
    points_name = coordinator.storage.get_points_name()
    if reward_said:
        reward = _best_match(rewards, reward_said)
        if reward is None:
            return _say(coordinator, "reward_not_found", reward_name=reward_said)
    else:
        affordable = [r for r in rewards if r.cost > child.points]
        reward = min(affordable, key=lambda r: r.cost) if affordable else max(rewards, key=lambda r: r.cost)
    missing = int(reward.cost) - int(child.points)
    if missing <= 0:
        return _say(coordinator, "reward_ready", child_name=child.name, reward_name=reward.name)
    return _say(
        coordinator,
        "reward_progress",
        child_name=child.name,
        reward_name=reward.name,
        missing=missing,
        points_name=points_name,
    )


async def async_complete_by_voice(hass, coordinator, name: str, chore_said: str, context=None) -> str:
    """Complete ``chore_said`` for ``name`` as the child would, and say what happened."""
    from . import authz
    from .watch import chore_needs_input

    child = _find_child(coordinator, name)
    if child is None:
        return _say(coordinator, "not_found", name=name)
    if context is not None and not await authz.async_context_allows_child(hass, coordinator, context, child.id):
        return _say(coordinator, "not_allowed", child_name=child.name)
    due = coordinator.get_due_chores_for_child(child.id)
    # A chore named exactly is that chore, done or not — "make bed" said twice
    # must not fall through to some other chore with "make bed" in its name.
    exact = next((c for c in coordinator.storage.get_chores() if _norm(c.name) == _norm(chore_said)), None)
    if exact is not None and all(c.id != exact.id for c in due):
        return _say(coordinator, "already_done", child_name=child.name, chore_name=exact.name)
    chore = exact or _best_match(due, chore_said)
    if chore is None:
        known = _best_match(coordinator.storage.get_chores(), chore_said)
        if known is not None:
            return _say(coordinator, "already_done", child_name=child.name, chore_name=known.name)
        return _say(coordinator, "chore_not_found", chore_name=chore_said)
    if chore_needs_input(coordinator, chore):
        return _say(coordinator, "needs_card", chore_name=chore.name)
    try:
        completion = await coordinator.async_complete_chore(chore.id, child.id)
    except ValueError as err:
        return str(err)
    if completion is None:
        return _say(coordinator, "already_done", child_name=child.name, chore_name=chore.name)
    if completion.approved:
        return _say(
            coordinator,
            "done",
            child_name=child.name,
            chore_name=chore.name,
            points=completion.points_awarded,
            points_name=coordinator.storage.get_points_name(),
        )
    return _say(coordinator, "done_pending", child_name=child.name, chore_name=chore.name)


def _slot(intent_obj, key: str) -> str:
    slot = (intent_obj.slots or {}).get(key) or {}
    return slot.get("value", "") if isinstance(slot, dict) else str(slot)


def _child_slot(intent_obj) -> str:
    """The child's name: ``child`` in the shipped sentences, ``name`` in older copies.

    ``{name}`` is the default agent's own slot for entity names, so a sentence
    using it never reaches TaskMate ("not aware of any device called …").
    """
    return (_slot(intent_obj, "child") or _slot(intent_obj, "name")).strip()


_CHILD_SLOTS = {vol.Optional("child"): cv.string, vol.Optional("name"): cv.string}


class _TaskMateIntentBase(intent.IntentHandler):
    slot_schema = dict(_CHILD_SLOTS)

    def _speech(self, coordinator, name: str) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    async def async_handle(self, intent_obj):
        hass = intent_obj.hass
        coordinator = _get_coordinator(hass)
        await _prepare_reply(intent_obj)
        response = intent_obj.create_response()
        response.async_set_speech(self._speech(coordinator, _child_slot(intent_obj)))
        return response


class ChoresLeftIntentHandler(_TaskMateIntentBase):
    intent_type = INTENT_CHORES_LEFT

    def _speech(self, coordinator, name: str) -> str:
        return chores_left_speech(coordinator, name)


class PointsIntentHandler(_TaskMateIntentBase):
    intent_type = INTENT_POINTS

    def _speech(self, coordinator, name: str) -> str:
        return points_speech(coordinator, name)


class NextChoreIntentHandler(_TaskMateIntentBase):
    intent_type = INTENT_NEXT_CHORE

    def _speech(self, coordinator, name: str) -> str:
        return next_chore_speech(coordinator, name)


class RewardProgressIntentHandler(intent.IntentHandler):
    intent_type = INTENT_REWARD_PROGRESS
    slot_schema = {**_CHILD_SLOTS, vol.Optional("reward"): cv.string}

    async def async_handle(self, intent_obj):
        coordinator = _get_coordinator(intent_obj.hass)
        await _prepare_reply(intent_obj)
        response = intent_obj.create_response()
        response.async_set_speech(
            reward_progress_speech(coordinator, _child_slot(intent_obj), _slot(intent_obj, "reward").strip())
        )
        return response


class CompleteChoreIntentHandler(intent.IntentHandler):
    intent_type = INTENT_COMPLETE_CHORE
    slot_schema = {**_CHILD_SLOTS, vol.Required("chore"): cv.string}

    async def async_handle(self, intent_obj):
        hass = intent_obj.hass
        coordinator = _get_coordinator(hass)
        await _prepare_reply(intent_obj)
        response = intent_obj.create_response()
        speech = await async_complete_by_voice(
            hass,
            coordinator,
            _child_slot(intent_obj),
            _slot(intent_obj, "chore").strip(),
            getattr(intent_obj, "context", None),
        )
        response.async_set_speech(speech)
        return response


def async_setup_intents(hass: HomeAssistant) -> None:
    """Register TaskMate conversation intents (idempotent enough for reloads)."""
    for handler in (
        ChoresLeftIntentHandler(),
        PointsIntentHandler(),
        CompleteChoreIntentHandler(),
        NextChoreIntentHandler(),
        RewardProgressIntentHandler(),
    ):
        intent.async_register(hass, handler)
    _LOGGER.debug("Registered TaskMate conversation intents")
