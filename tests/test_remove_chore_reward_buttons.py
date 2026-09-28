"""Deleting a chore or reward takes its buttons with it (#960).

The per-child complete/claim buttons used to stay in the entity registry
after their chore or reward was deleted (or the child was unassigned), and HA
restored them as ``unavailable`` on every restart. The button platform now
drops them as they go, and a setup-time sweep clears what existing installs
already carry.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import custom_components.taskmate.button as button_mod
import custom_components.taskmate.coordinator as coord_mod
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, Reward
from custom_components.taskmate.storage import TaskMateStorage

from .conftest import FakeStore

ENTRY = "entry1"
A = "aaaaaaaaaaaaaaaa"
B = "bbbbbbbbbbbbbbbb"
DISHES = "1111111111111111"
BINS = "2222222222222222"
TV = "3333333333333333"
TREAT = "4444444444444444"


def _uid(child: str, item: str, kind: str) -> str:
    return f"{ENTRY}_{child}_{item}_{kind}"


class FakeRegistry:
    """Entity registry holding entity_id -> unique_id for one config entry."""

    def __init__(self):
        self.entries: dict[str, str] = {}
        self._seq = 0

    def add(self, *unique_ids: str, domain: str = "button") -> None:
        for uid in unique_ids:
            self._seq += 1
            self.entries[f"{domain}.e{self._seq}"] = uid

    def async_remove(self, entity_id: str) -> None:
        self.entries.pop(entity_id)

    def remaining(self) -> set[str]:
        return set(self.entries.values())


@pytest.fixture
def registry(monkeypatch):
    reg = FakeRegistry()
    reg.queried = []

    def _entries(r, entry_id):
        r.queried.append(entry_id)
        pool = r.entries if entry_id == ENTRY else {}
        return [SimpleNamespace(entity_id=eid, unique_id=uid, domain=eid.split(".")[0]) for eid, uid in pool.items()]

    monkeypatch.setattr(
        coord_mod, "er", SimpleNamespace(async_get=lambda hass: reg, async_entries_for_config_entry=_entries)
    )
    return reg


def _storage(chores: list[Chore], rewards: list[Reward]) -> TaskMateStorage:
    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = ENTRY
    storage._store = FakeStore(None, 1, "test")
    storage._data = {
        "children": [Child(name="Ann", id=A).to_dict(), Child(name="Ben", id=B).to_dict()],
        "chores": [c.to_dict() for c in chores],
        "rewards": [r.to_dict() for r in rewards],
    }
    storage._data_version = 0
    return storage


def _coord(storage: TaskMateStorage) -> TaskMateCoordinator:
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.entry_id = ENTRY
    coord.storage = storage
    coord._listeners = []
    coord.async_add_listener = lambda cb: coord._listeners.append(cb)
    coord._rebuild_data = lambda: setattr(
        coord,
        "data",
        {
            "children": storage.get_children(),
            "chores": storage.get_chores(),
            "rewards": storage.get_rewards(),
        },
    )
    coord._rebuild_data()
    return coord


def _family():
    chores = [
        Chore(name="Dishes", points=5, id=DISHES),
        Chore(name="Bins", points=5, id=BINS, assigned_to=[A, B]),
    ]
    rewards = [Reward(name="TV", cost=10, id=TV), Reward(name="Treat", cost=5, id=TREAT)]
    return chores, rewards


def _setup_platform(coord: TaskMateCoordinator, registry: FakeRegistry) -> list:
    """Run the button platform setup; mirror added entities into the registry."""
    added: list = []

    def _add(entities):
        added.extend(entities)
        registry.add(*(e._attr_unique_id for e in entities))

    entry = MagicMock()
    entry.entry_id = ENTRY
    hass = MagicMock()
    hass.data = {DOMAIN: {ENTRY: coord}}
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(button_mod.async_setup_entry(hass, entry, _add))
    finally:
        loop.close()
    return added


def _update(coord: TaskMateCoordinator) -> None:
    """Simulate a coordinator refresh: rebuild data, fire listeners."""
    coord._rebuild_data()
    for cb in coord._listeners:
        cb()


def _all_live_uids() -> set[str]:
    return {
        _uid(A, DISHES, "complete"),
        _uid(B, DISHES, "complete"),
        _uid(A, BINS, "complete"),
        _uid(B, BINS, "complete"),
        _uid(A, TV, "claim"),
        _uid(B, TV, "claim"),
        _uid(A, TREAT, "claim"),
        _uid(B, TREAT, "claim"),
    }


# ── live deletions / assignment changes ─────────────────────────────────────


def test_platform_creates_the_expected_buttons(registry):
    coord = _coord(_storage(*_family()))
    _setup_platform(coord, registry)
    assert registry.remaining() == _all_live_uids()


def test_deleting_a_chore_removes_its_buttons(registry):
    storage = _storage(*_family())
    coord = _coord(storage)
    _setup_platform(coord, registry)

    storage.remove_chore(BINS)
    _update(coord)

    assert registry.remaining() == _all_live_uids() - {_uid(A, BINS, "complete"), _uid(B, BINS, "complete")}


def test_deleting_a_reward_removes_its_buttons(registry):
    storage = _storage(*_family())
    coord = _coord(storage)
    _setup_platform(coord, registry)

    storage.remove_reward(TV)
    _update(coord)

    assert registry.remaining() == _all_live_uids() - {_uid(A, TV, "claim"), _uid(B, TV, "claim")}


def test_unassigning_a_child_removes_only_their_button_and_reassigning_restores_it(registry):
    storage = _storage(*_family())
    coord = _coord(storage)
    added = _setup_platform(coord, registry)

    bins = storage.get_chore(BINS)
    bins.assigned_to = [A]
    storage.update_chore(bins)
    _update(coord)
    assert registry.remaining() == _all_live_uids() - {_uid(B, BINS, "complete")}

    bins.assigned_to = [A, B]
    storage.update_chore(bins)
    _update(coord)
    assert registry.remaining() == _all_live_uids()
    assert added[-1]._attr_unique_id == _uid(B, BINS, "complete")


def test_switching_a_chore_to_unassigned_removes_its_buttons(registry):
    storage = _storage(*_family())
    coord = _coord(storage)
    _setup_platform(coord, registry)

    dishes = storage.get_chore(DISHES)
    dishes.assignment_mode = "unassigned"
    storage.update_chore(dishes)
    _update(coord)

    assert registry.remaining() == _all_live_uids() - {_uid(A, DISHES, "complete"), _uid(B, DISHES, "complete")}


def test_an_unchanged_refresh_removes_nothing(registry):
    coord = _coord(_storage(*_family()))
    _setup_platform(coord, registry)
    registry.add(f"{ENTRY}_overall_stats", domain="sensor")
    _update(coord)
    assert registry.remaining() == _all_live_uids() | {f"{ENTRY}_overall_stats"}


# ── setup-time sweep for installs affected before the fix ───────────────────


GONE_CHORE = "5555555555555555"
GONE_REWARD = "6666666666666666"


def test_setup_sweep_removes_buttons_of_deleted_chores_and_rewards(registry):
    chores, rewards = _family()
    chores[1].assigned_to = [A]  # Ben was taken off the bins after his button was made
    coord = _coord(_storage(chores, rewards))
    stale = {
        _uid(A, GONE_CHORE, "complete"),
        _uid(B, GONE_CHORE, "complete"),
        _uid(A, GONE_REWARD, "claim"),
        _uid(B, BINS, "complete"),
    }
    kept_live = _all_live_uids() - {_uid(B, BINS, "complete")}
    registry.add(*stale, *kept_live)

    assert coord.async_prune_orphan_button_entities() == len(stale)
    assert registry.remaining() == kept_live


def test_setup_sweep_keeps_anything_it_cannot_positively_parse(registry):
    coord = _coord(_storage(*_family()))
    unparsed = [
        f"{ENTRY}_{A}_sectest_chore_complete",  # non-generated chore id
        f"{ENTRY}_{A}_{GONE_CHORE}_completed",  # unknown suffix
        f"{ENTRY}_{A}_{GONE_CHORE}",  # no suffix
        f"{ENTRY}_{A}_{GONE_REWARD}_claim_extra",
        f"{ENTRY}_{GONE_CHORE}_complete",  # no child segment
    ]
    registry.add(*unparsed)
    # A sensor whose unique id happens to have the button shape is not a button.
    registry.add(_uid(A, GONE_CHORE, "complete"), domain="sensor")
    registry.add(f"{ENTRY}_{A}_points", f"{ENTRY}_overall_stats", domain="sensor")

    assert coord.async_prune_orphan_button_entities() == 0
    assert registry.remaining() == set(unparsed) | {
        _uid(A, GONE_CHORE, "complete"),
        f"{ENTRY}_{A}_points",
        f"{ENTRY}_overall_stats",
    }


def test_setup_sweep_leaves_other_config_entries_alone(registry):
    coord = _coord(_storage(*_family()))
    other = f"other_{A}_{GONE_CHORE}_complete"
    registry.add(other)
    assert coord.async_prune_orphan_button_entities() == 0
    assert registry.remaining() == {other}
    assert registry.queried == [ENTRY]
