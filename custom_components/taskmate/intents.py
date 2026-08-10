"""Home Assistant conversation intents for TaskMate (FEAT-12).

Registers intent handlers so a voice/text assistant can answer questions like
"how many chores does Malia have left?" or "how many stars does Alex have?".

The default conversation agent matches *sentences* to these intent names; ship
the example sentences in ``custom_sentences/<lang>/taskmate.yaml`` into your HA
config (see custom_sentences/README.md). The speech-building logic is kept in
pure helpers so it is unit-testable without the conversation stack.
"""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

INTENT_CHORES_LEFT = "TaskMateChoresLeft"
INTENT_POINTS = "TaskMatePoints"


def _get_coordinator(hass: HomeAssistant):
    from .coordinator import TaskMateCoordinator

    for value in hass.data.get(DOMAIN, {}).values():
        if isinstance(value, TaskMateCoordinator):
            return value
    return None


def _find_child(coordinator, name: str):
    """Case-insensitive child lookup by name."""
    if coordinator is None or not name:
        return None
    target = name.strip().lower()
    for child in coordinator.storage.get_children():
        if child.name.strip().lower() == target:
            return child
    return None


def chores_left_speech(coordinator, name: str) -> str:
    """Speech for 'how many chores does <name> have left'."""
    child = _find_child(coordinator, name)
    if child is None:
        return f"I couldn't find anyone called {name}."
    count = len(coordinator.get_due_chores_for_child(child.id))
    if count == 0:
        return f"{child.name} has finished all their chores. Nice work!"
    if count == 1:
        return f"{child.name} has 1 chore left today."
    return f"{child.name} has {count} chores left today."


def points_speech(coordinator, name: str) -> str:
    """Speech for 'how many points does <name> have'."""
    child = _find_child(coordinator, name)
    if child is None:
        return f"I couldn't find anyone called {name}."
    points_name = coordinator.storage.get_points_name()
    return f"{child.name} has {child.points} {points_name}."


class _TaskMateIntentBase(intent.IntentHandler):
    slot_schema = {vol.Required("name"): cv.string}

    def _speech(self, coordinator, name: str) -> str:  # pragma: no cover - overridden
        raise NotImplementedError

    async def async_handle(self, intent_obj):
        hass = intent_obj.hass
        coordinator = _get_coordinator(hass)
        name = ""
        slot = (intent_obj.slots or {}).get("name") or {}
        name = slot.get("value", "") if isinstance(slot, dict) else str(slot)
        response = intent_obj.create_response()
        response.async_set_speech(self._speech(coordinator, name))
        return response


class ChoresLeftIntentHandler(_TaskMateIntentBase):
    intent_type = INTENT_CHORES_LEFT

    def _speech(self, coordinator, name: str) -> str:
        return chores_left_speech(coordinator, name)


class PointsIntentHandler(_TaskMateIntentBase):
    intent_type = INTENT_POINTS

    def _speech(self, coordinator, name: str) -> str:
        return points_speech(coordinator, name)


def async_setup_intents(hass: HomeAssistant) -> None:
    """Register TaskMate conversation intents (idempotent enough for reloads)."""
    intent.async_register(hass, ChoresLeftIntentHandler())
    intent.async_register(hass, PointsIntentHandler())
    _LOGGER.debug("Registered TaskMate conversation intents")
