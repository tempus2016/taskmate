"""Translated entity names must never move an entity id (#1234).

The cards default to the entity ids Home Assistant built from TaskMate's
English names (`sensor.taskmate_overview`, ...). Home Assistant derives a new
entity's id from `suggested_object_id` and `has_entity_name` alone (plus the
device), so the contract is:

* `has_entity_name` stays off — turning it on makes HA 2024.7-2026.5 prefix
  the device name ("Malia Points" -> `sensor.taskmate_malia_points` instead of
  `sensor.malia_points`) and makes the id follow the translated name;
* `suggested_object_id` is byte-identical to the English name the entity
  carried before names were translated;
* `name` is the translation for HA's language, falling back to English.

The last class of tests reads strings.json / translations/*.json and only
passes once the entity-name strings have been merged into them.
"""

from __future__ import annotations

import json
import pathlib
import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.taskmate import sensor as sensor_mod
from custom_components.taskmate.binary_sensor import HasPendingApprovalsBinarySensor
from custom_components.taskmate.button import ClaimRewardButton, CompleteChoreButton
from custom_components.taskmate.entity_names import ENGLISH_NAMES
from custom_components.taskmate.models import Child, Chore, Reward

# Reuse the EventEntity stub that test_event_entities installs, so both files
# see the same event module whichever is collected first.
from .test_event_entities import tm_event

TaskMateChildEvent = tm_event.TaskMateChildEvent
TaskMateFamilyEvent = tm_event.TaskMateFamilyEvent

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
LANGS = ("en", "en-GB", "da", "de", "fr", "nb", "nl", "nn", "pl", "pt", "pt-BR")

ENTRY = MagicMock(entry_id="e1")
MALIA = Child(name="Malia", id="ch1")
DISHES = Chore(name="Dishes", points=5, id="cho1")
ICE_CREAM = Reward(name="Ice Cream", cost=30, id="rw1")


def _coord():
    coord = MagicMock()
    coord.data = {}
    return coord


# (factory, platform, translation_key, the exact name the entity had before
# names were translated — i.e. the string HA built today's entity id from).
CASES = [
    (lambda: sensor_mod.TaskMateOverallStatsSensor(_coord(), ENTRY), "sensor", "overview", "TaskMate Overview"),
    (lambda: sensor_mod.TaskMateChoresSensor(_coord(), ENTRY), "sensor", "chores", "TaskMate Chores"),
    (
        lambda: sensor_mod.TaskMateChoreAvailabilitySensor(_coord(), ENTRY),
        "sensor",
        "chore_availability",
        "TaskMate Chore Availability",
    ),
    (lambda: sensor_mod.TaskMateRewardsSensor(_coord(), ENTRY), "sensor", "rewards", "TaskMate Rewards"),
    (lambda: sensor_mod.TaskMateActivitySensor(_coord(), ENTRY), "sensor", "activity", "TaskMate Activity"),
    (lambda: sensor_mod.TaskMateIncentivesSensor(_coord(), ENTRY), "sensor", "incentives", "TaskMate Incentives"),
    (lambda: sensor_mod.TaskMateBountiesSensor(_coord(), ENTRY), "sensor", "bounties", "TaskMate Bounties"),
    (lambda: sensor_mod.TaskMateAuctionsSensor(_coord(), ENTRY), "sensor", "auctions", "TaskMate Auctions"),
    (lambda: sensor_mod.TaskMateChoreBoardSensor(_coord(), ENTRY), "sensor", "chore_board", "TaskMate Chore Board"),
    (lambda: sensor_mod.ChildPointsSensor(_coord(), ENTRY, MALIA), "sensor", "child_points", "Malia Points"),
    (lambda: sensor_mod.ChildStatsSensor(_coord(), ENTRY, MALIA), "sensor", "child_stats", "Malia Stats"),
    (lambda: sensor_mod.ChildWishlistSensor(_coord(), ENTRY, MALIA), "sensor", "child_wishlist", "Malia Wishlist"),
    (lambda: sensor_mod.ChildWatchSensor(_coord(), ENTRY, MALIA), "sensor", "child_watch", "Malia Watch"),
    (lambda: sensor_mod.ChildBadgesSensor(_coord(), ENTRY, MALIA), "sensor", "child_badges", "Malia Badges"),
    (lambda: sensor_mod.PendingApprovalsSensor(_coord(), ENTRY), "sensor", "pending_approvals", "Pending Approvals"),
    (
        lambda: HasPendingApprovalsBinarySensor(_coord(), ENTRY),
        "binary_sensor",
        "has_pending_approvals",
        "Has Pending Approvals",
    ),
    (
        lambda: CompleteChoreButton(_coord(), ENTRY, MALIA, DISHES),
        "button",
        "complete_chore",
        "Malia: Complete Dishes",
    ),
    (
        lambda: ClaimRewardButton(_coord(), ENTRY, MALIA, ICE_CREAM),
        "button",
        "claim_reward",
        "Malia: Claim Ice Cream",
    ),
    (lambda: TaskMateChildEvent(ENTRY, MALIA.id, MALIA.name), "event", "child_activity", "Malia activity"),
    (lambda: TaskMateFamilyEvent(ENTRY), "event", "family_activity", "Family activity"),
]
IDS = [f"{platform}.{key}" for _, platform, key, _ in CASES]


def _with_translations(entity, platform: str, translations: dict[str, str], *, legacy: bool = False):
    """Attach loaded translations the way HA does (2024.7: `platform`; newer: `platform_data`)."""
    data = SimpleNamespace(platform_translations=translations, platform_name="taskmate", domain=platform)
    if legacy:
        entity.platform_data = None
        entity.platform = data
    else:
        entity.platform_data = data
    return entity


def test_every_english_name_is_covered():
    """A new translated entity must be added to CASES so its id is pinned."""
    covered = {(platform, key) for _, platform, key, _ in CASES}
    declared = {(platform, key) for platform, keys in ENGLISH_NAMES.items() for key in keys}
    assert covered == declared


@pytest.mark.parametrize(("factory", "platform", "key", "old_name"), CASES, ids=IDS)
class TestObjectIdUnchanged:
    def test_suggested_object_id_is_the_old_english_name(self, factory, platform, key, old_name):
        assert factory().suggested_object_id == old_name

    def test_has_entity_name_stays_off(self, factory, platform, key, old_name):
        """With it on, HA would prefix the device name to the id on 2024.7-2026.5."""
        assert getattr(factory(), "_attr_has_entity_name", False) is not True

    def test_does_not_set_attr_name(self, factory, platform, key, old_name):
        """`_attr_name` would bypass the translation lookup."""
        assert "_attr_name" not in vars(factory())

    def test_translation_key(self, factory, platform, key, old_name):
        assert factory()._attr_translation_key == key

    def test_name_falls_back_to_english_without_translations(self, factory, platform, key, old_name):
        assert factory().name == old_name

    @pytest.mark.parametrize("legacy", [False, True], ids=["platform_data", "ha_2024_7_platform"])
    def test_translated_name_leaves_object_id_alone(self, factory, platform, key, old_name, legacy):
        template = "Übersetzt " + " ".join(f"{{{p}}}" for p in re.findall(r"\{(\w+)\}", ENGLISH_NAMES[platform][key]))
        entity = _with_translations(
            factory(), platform, {f"component.taskmate.entity.{platform}.{key}.name": template}, legacy=legacy
        )
        assert entity.name.startswith("Übersetzt")
        if "{child}" in template:
            assert "Malia" in entity.name
        assert entity.suggested_object_id == old_name

    def test_broken_translation_falls_back_to_english(self, factory, platform, key, old_name):
        entity = _with_translations(
            factory(), platform, {f"component.taskmate.entity.{platform}.{key}.name": "Kaputt {nope}"}
        )
        assert entity.name == old_name
        assert entity.suggested_object_id == old_name


def test_child_name_with_braces_is_kept_verbatim():
    kid = Child(name="Al {x}", id="ch9")
    entity = sensor_mod.ChildPointsSensor(_coord(), ENTRY, kid)
    assert entity.suggested_object_id == "Al {x} Points"
    _with_translations(entity, "sensor", {"component.taskmate.entity.sensor.child_points.name": "Punkte von {child}"})
    assert entity.name == "Punkte von Al {x}"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


@pytest.mark.parametrize(
    ("factory", "expected_legacy", "expected_2026_6"),
    [
        # HA <= 2026.5: object id = slug(name). HA >= 2026.6: the device name
        # ("TaskMate") prefixes it unless the name already starts with it.
        (CASES[0][0], "sensor.taskmate_overview", "sensor.taskmate_overview"),
        (CASES[9][0], "sensor.malia_points", "sensor.taskmate_malia_points"),
        (CASES[14][0], "sensor.pending_approvals", "sensor.taskmate_pending_approvals"),
    ],
    ids=["overview", "child_points", "pending_approvals"],
)
def test_representative_entity_ids(factory, expected_legacy, expected_2026_6):
    """Spell out the ids for German HA: the translated name is not used."""
    entity = factory()
    platform = expected_legacy.split(".")[0]
    _with_translations(entity, platform, {f"component.taskmate.entity.{platform}.{entity._tm_name_key}.name": "X"})
    obj = entity.suggested_object_id
    assert f"{platform}.{_slug(obj)}" == expected_legacy
    stripped = obj[len("TaskMate") :].lstrip(" -:") if obj.startswith("TaskMate") else obj
    assert f"{platform}.{_slug('TaskMate ' + stripped)}" == expected_2026_6


# ── Strings: pass only once the entity-name strings are merged ──────────────


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _catalogues():
    yield "strings.json", _load(ROOT / "strings.json")
    for lang in LANGS:
        yield f"translations/{lang}.json", _load(ROOT / "translations" / f"{lang}.json")


@pytest.mark.parametrize(("platform", "key"), [(p, k) for p, keys in ENGLISH_NAMES.items() for k in keys])
def test_name_strings_exist_with_matching_placeholders(platform, key):
    english = ENGLISH_NAMES[platform][key]
    want = sorted(re.findall(r"\{(\w+)\}", english))
    for label, data in _catalogues():
        name = data.get("entity", {}).get(platform, {}).get(key, {}).get("name")
        assert isinstance(name, str) and name, f"{label}: entity.{platform}.{key}.name missing"
        assert sorted(re.findall(r"\{(\w+)\}", name)) == want, f"{label}: placeholders differ in {name!r}"
        assert not re.search(r"['’][{}]", name), f"{label}: apostrophe before a brace in {name!r}"
        if label in ("strings.json", "translations/en.json"):
            # The English text is the entity id source; it must not drift.
            assert name == english, f"{label}: {name!r} != ENGLISH_NAMES {english!r}"
