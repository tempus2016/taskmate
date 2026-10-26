"""Event platform for TaskMate.

One ``event`` entity per child, plus one for the family, re-publishing the
``taskmate_*`` bus events. The bus events have always been there for YAML
automations; event entities make the same moments pickable in the UI
automation editor ("When Malia's TaskMate activity has event type
chore_approved"), and show the latest one on a dashboard.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    NOTIF_TYPE_HELP_REQUESTED,
    NOTIF_TYPE_PENALTY_REDEEMED,
    NOTIF_TYPE_PET_EVOLVED,
    NOTIF_TYPE_RAFFLE_DRAWN,
    NOTIF_TYPE_WEEKLY_GOAL_REACHED,
)
from .coord_notifications import notification_event_name
from .coordinator import TaskMateCoordinator
from .entity import taskmate_device_info

# Bus events that are about one child, by the event type the entity reports.
# Moments that only a notification announces take that notification's event
# name, so they stay right if the feature ever fires its own event (#1014).
CHILD_EVENTS: dict[str, str] = {
    "chore_completed": "taskmate_chore_completed",
    "chore_approved": "taskmate_chore_approved",
    "chore_rejected": "taskmate_chore_rejected",
    "chore_approval_undone": "taskmate_chore_approval_undone",
    "reward_claimed": "taskmate_reward_claimed",
    "reward_approved": "taskmate_reward_approved",
    "reward_rejected": "taskmate_reward_rejected",
    "badge_earned": "taskmate_badge_earned",
    "level_up": "taskmate_level_up",
    "streak_updated": "taskmate_streak_updated",
    "streak_freeze_used": "taskmate_streak_freeze_used",
    "perfect_week": "taskmate_perfect_week",
    "weekly_target_reached": "taskmate_weekly_target_reached",
    "quest_completed": "taskmate_quest_completed",
    "challenge_completed": "taskmate_challenge_completed",
    "bonus_applied": "taskmate_bonus_applied",
    "penalty_applied": "taskmate_penalty_applied",
    "surprise_bonus": "taskmate_surprise_bonus",
    "mandatory_missed": "taskmate_mandatory_missed",
    "team_chore_completed": "taskmate_team_chore_completed",
    "points_gifted": "taskmate_points_gifted",
    "help_requested": notification_event_name(NOTIF_TYPE_HELP_REQUESTED),
    "mood_logged": "taskmate_mood_logged",
    "weekly_goal_reached": notification_event_name(NOTIF_TYPE_WEEKLY_GOAL_REACHED),
    "sick_day": "taskmate_sick_day",
    "chore_auto_approved": "taskmate_chore_auto_approved",
    "penalty_redeemed": notification_event_name(NOTIF_TYPE_PENALTY_REDEEMED),
    "raffle_won": "taskmate_raffle_won",
    "pet_evolved": notification_event_name(NOTIF_TYPE_PET_EVOLVED),
    "reward_delivered": "taskmate_reward_delivered",
    "personal_best": "taskmate_personal_best",
    "appeal_submitted": "taskmate_appeal_submitted",
    "appeal_decided": "taskmate_appeal_decided",
    "screen_time_low": "taskmate_screen_time_low",
    "screen_time_out": "taskmate_screen_time_out",
    "screen_time_changed": "taskmate_screen_time_changed",
    "screen_time_saved": "taskmate_screen_time_saved",
    "screen_time_jar_opened": "taskmate_screen_time_jar_opened",
    "points_expired": "taskmate_points_expired",
    "points_expiring": "taskmate_points_expiring",
    "reward_rated": "taskmate_reward_rated",
    "penalty_warning": "taskmate_penalty_warning",
    "sibling_check": "taskmate_sibling_check",
}

# Bus events about the whole family.
FAMILY_EVENTS: dict[str, str] = {
    "family_goal_reached": "taskmate_family_goal_reached",
    "season_champion": "taskmate_season_champion",
    "bounty_posted": "taskmate_bounty_posted",
    "scheduled_change_applied": "taskmate_scheduled_change_applied",
    "raffle_drawn": notification_event_name(NOTIF_TYPE_RAFFLE_DRAWN),
    "boost_started": "taskmate_boost_started",
    "boost_ended": "taskmate_boost_ended",
    "bin_day": "taskmate_bin_day",
    "shopping_job": "taskmate_shopping_job",
}

# Payload keys never copied onto the entity: they are long, internal, or the
# child's own words. The bus event is for automations; the entity's state is
# readable by every HA user, and the sensors already keep a help request's
# message, an appeal's reasoning and a rejection's note off the state machine.
_SKIP_ATTRS = {"timestamp", "message", "message_text", "note", "reason", "request_id"}


def _child_ids(data: dict[str, Any]) -> set[str]:
    """Every child a bus event is about.

    Most carry ``child_id``; a gift names both sides, and a teamwork chore
    lists everyone in the team.
    """
    ids = {data.get("child_id"), data.get("from_child_id"), data.get("to_child_id")}
    for key in ("child_ids", "team"):
        value = data.get(key)
        if isinstance(value, list):
            ids.update(v for v in value if isinstance(v, str))
    return {i for i in ids if isinstance(i, str) and i}


def _attributes(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k not in _SKIP_ATTRS and isinstance(v, (str, int, float, bool))}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaskMate event entities."""
    coordinator: TaskMateCoordinator = hass.data[DOMAIN][entry.entry_id]
    by_child: dict[str, TaskMateChildEvent] = {}
    family = TaskMateFamilyEvent(entry)

    def _new_children() -> list[TaskMateChildEvent]:
        added = []
        for child in coordinator.data.get("children", []):
            if child.id not in by_child:
                entity = TaskMateChildEvent(entry, child.id, child.name)
                by_child[child.id] = entity
                added.append(entity)
        return added

    async_add_entities([family, *_new_children()])

    @callback
    def _children_changed() -> None:
        if added := _new_children():
            async_add_entities(added)

    entry.async_on_unload(coordinator.async_add_listener(_children_changed))

    def _make_child_listener(event_type: str):
        @callback
        def _on_event(event: Event) -> None:
            for child_id in _child_ids(event.data or {}):
                if entity := by_child.get(child_id):
                    entity.handle(event_type, event.data or {})

        return _on_event

    def _make_family_listener(event_type: str):
        @callback
        def _on_event(event: Event) -> None:
            family.handle(event_type, event.data or {})

        return _on_event

    for event_type, bus_event in CHILD_EVENTS.items():
        entry.async_on_unload(hass.bus.async_listen(bus_event, _make_child_listener(event_type)))
    for event_type, bus_event in FAMILY_EVENTS.items():
        entry.async_on_unload(hass.bus.async_listen(bus_event, _make_family_listener(event_type)))


class _TaskMateEventBase(EventEntity):
    """Shared behaviour: fire only once HA has the entity."""

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return taskmate_device_info(self._entry.entry_id)

    @callback
    def handle(self, event_type: str, data: dict[str, Any]) -> None:
        if self.hass is None or event_type not in self.event_types:
            return
        self._trigger_event(event_type, _attributes(data))
        self.async_write_ha_state()


class TaskMateChildEvent(_TaskMateEventBase):
    """A child's TaskMate moments as one event entity."""

    _attr_translation_key = "child_activity"
    _attr_icon = "mdi:account-star"
    _attr_event_types = list(CHILD_EVENTS)

    def __init__(self, entry: ConfigEntry, child_id: str, child_name: str) -> None:
        super().__init__(entry)
        self.child_id = child_id
        self._attr_unique_id = f"{entry.entry_id}_{child_id}_activity_event"
        self._attr_name = f"{child_name} activity"


class TaskMateFamilyEvent(_TaskMateEventBase):
    """Family-wide TaskMate moments."""

    _attr_translation_key = "family_activity"
    _attr_icon = "mdi:home-heart"
    _attr_event_types = list(FAMILY_EVENTS)

    def __init__(self, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_family_activity_event"
        self._attr_name = "Family activity"
