"""Translated entity names that never move an entity id.

TaskMate's entities were named in English with `has_entity_name` off, and the
cards default to the entity ids Home Assistant built from those English names
(`sensor.taskmate_overview`, `sensor.taskmate_pending_approvals`, ...).

Switching to `has_entity_name = True` would let Home Assistant translate the
name, but it also changes how the entity id is built: on HA 2024.7-2026.5 the
device name is glued in front ("Malia Points" -> `sensor.taskmate_malia_points`
instead of `sensor.malia_points`), and new installs on a TaskMate language
would get ids in that language (`sensor.taskmate_ubersicht`). Either breaks the
cards for a fresh install.

So the entities keep `has_entity_name` off — Home Assistant then derives the
entity id exactly as it always has, from `suggested_object_id` — and this mixin
supplies both halves itself:

* `suggested_object_id` is always today's English name, so the id is the same
  byte for byte on every Home Assistant version;
* `name` (what users see) is looked up in the integration's entity
  translations for the configured language, falling back to the English name.

`ENGLISH_NAMES` is the single source for the English text; the `en` entries in
`strings.json` / `translations/en.json` must match it (tested).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .const import DOMAIN

# platform -> translation_key -> English name template. Changing one of these
# changes the entity id of every NEW install — don't.
ENGLISH_NAMES: dict[str, dict[str, str]] = {
    "sensor": {
        "overview": "TaskMate Overview",
        "chores": "TaskMate Chores",
        "chore_availability": "TaskMate Chore Availability",
        "rewards": "TaskMate Rewards",
        "activity": "TaskMate Activity",
        "incentives": "TaskMate Incentives",
        "bounties": "TaskMate Bounties",
        "auctions": "TaskMate Auctions",
        "chore_board": "TaskMate Chore Board",
        "child_points": "{child} Points",
        "child_stats": "{child} Stats",
        "child_wishlist": "{child} Wishlist",
        "child_watch": "{child} Watch",
        "child_badges": "{child} Badges",
        "pending_approvals": "Pending Approvals",
    },
    "binary_sensor": {
        "has_pending_approvals": "Has Pending Approvals",
    },
    "button": {
        "complete_chore": "{child}: Complete {chore}",
        "claim_reward": "{child}: Claim {reward}",
    },
    "event": {
        "child_activity": "{child} activity",
        "family_activity": "Family activity",
    },
}


def english_name(platform: str, key: str, placeholders: Mapping[str, str] | None = None) -> str:
    """The English name (and object id source) of an entity."""
    return ENGLISH_NAMES[platform][key].format(**(placeholders or {}))


class TranslatedNameMixin:
    """Translated `name`, English `suggested_object_id`.

    List it before the Home Assistant entity classes so its properties win,
    and call `_set_translated_name` from `__init__` instead of setting
    `_attr_name`. Leave `has_entity_name` off: with it on, Home Assistant
    would prefix the device name to the entity id on older versions.
    """

    _tm_platform: str | None = None
    _tm_name_key: str | None = None
    _tm_placeholders: dict[str, str]

    def _set_translated_name(self, platform: str, key: str, **placeholders: str) -> None:
        ENGLISH_NAMES[platform][key]  # noqa: B018 - fail fast on an unknown key
        self._tm_platform = platform
        self._tm_name_key = key
        self._tm_placeholders = {k: str(v) for k, v in placeholders.items()}
        self._attr_translation_key = key
        self._attr_translation_placeholders = self._tm_placeholders

    @property
    def _english_name(self) -> str | None:
        if self._tm_platform is None or self._tm_name_key is None:
            return None
        return english_name(self._tm_platform, self._tm_name_key, self._tm_placeholders)

    def _translated_name(self) -> str | None:
        """The name in HA's configured language, if its translations are loaded."""
        # HA 2024.7 exposes the loaded translations on `entity.platform`;
        # newer releases moved them to `entity.platform_data`.
        source: Any = getattr(self, "platform_data", None) or getattr(self, "platform", None)
        translations = getattr(source, "platform_translations", None)
        if not translations or not isinstance(translations, Mapping):
            return None
        template = translations.get(f"component.{DOMAIN}.entity.{self._tm_platform}.{self._tm_name_key}.name")
        if not isinstance(template, str) or not template:
            return None
        try:
            return template.format(**self._tm_placeholders)
        except (KeyError, IndexError, ValueError):
            # A broken translation must never blank the entity's name.
            return None

    @property
    def name(self) -> str | None:  # type: ignore[override]
        english = self._english_name
        if english is None:
            return super().name  # type: ignore[misc]
        return self._translated_name() or english

    @property
    def suggested_object_id(self) -> str | None:  # type: ignore[override]
        english = self._english_name
        if english is None:
            return super().suggested_object_id  # type: ignore[misc]
        return english
