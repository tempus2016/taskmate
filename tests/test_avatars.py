"""Tests for avatar unlockables."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coord_avatars import DEFAULT_AVATAR_CATALOG
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _coord(child, catalog=None, xp_step=100):
    coord = object.__new__(TaskMateCoordinator)
    settings = {}
    if catalog is not None:
        settings["avatar_catalog"] = catalog
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d=None: settings.get(k, d))
    storage.set_setting = MagicMock(side_effect=lambda k, v: settings.__setitem__(k, v))
    storage.update_child = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord._settings = settings
    coord.get_child = MagicMock(return_value=child)
    coord.async_refresh = AsyncMock()
    # level_info derives from total_points_earned // step + 1
    coord.level_info = lambda c: {"level": int(getattr(c, "total_points_earned", 0) or 0) // xp_step + 1}
    return coord


def test_default_catalog_used_when_unset():
    coord = _coord(Child(name="A", id="a"))
    assert len(coord.avatar_catalog()) == len(DEFAULT_AVATAR_CATALOG)


def test_unlock_by_level_points_streak():
    child = Child(name="A", id="a", total_points_earned=500, best_streak=7)
    coord = _coord(child)  # level = 500//100+1 = 6
    opts = {o["icon"]: o for o in coord.avatar_options_for_child(child)}
    assert opts["mdi:account-circle"]["unlocked"]  # free
    assert opts["mdi:rocket-launch"]["unlocked"]  # level 3
    assert opts["mdi:robot-happy"]["unlocked"]  # level 5
    assert not opts["mdi:ninja"]["unlocked"]  # level 10
    assert opts["mdi:crown"]["unlocked"]  # 500 points
    assert not opts["mdi:trophy"]["unlocked"]  # 1000 points
    assert opts["mdi:fire"]["unlocked"]  # 7-day streak
    assert not opts["mdi:diamond-stone"]["unlocked"]  # 30-day streak


def test_child_cannot_select_locked_avatar():
    child = Child(name="A", id="a", total_points_earned=0, best_streak=0)
    coord = _coord(child)
    with pytest.raises(ValueError, match="not unlocked"):
        run(coord.async_set_avatar("a", "mdi:ninja", enforce_unlock=True))


def test_child_can_select_unlocked_avatar():
    child = Child(name="A", id="a", total_points_earned=0, best_streak=0)
    coord = _coord(child)
    run(coord.async_set_avatar("a", "mdi:account-circle", enforce_unlock=True))
    assert child.avatar == "mdi:account-circle"


def test_parent_can_set_locked_avatar():
    child = Child(name="A", id="a", total_points_earned=0, best_streak=0)
    coord = _coord(child)
    run(coord.async_set_avatar("a", "mdi:diamond-stone", enforce_unlock=False))
    assert child.avatar == "mdi:diamond-stone"


def test_set_unknown_avatar_rejected():
    child = Child(name="A", id="a")
    coord = _coord(child)
    with pytest.raises(ValueError, match="catalogue"):
        run(coord.async_set_avatar("a", "mdi:not-in-catalog", enforce_unlock=False))


def test_update_catalog_filters_iconless_rows():
    coord = _coord(Child(name="A", id="a"))
    run(
        coord.async_update_avatar_catalog(
            [
                {"label": "No icon", "icon": "", "unlock_type": "free"},
                {"label": "Good", "icon": "mdi:star", "unlock_type": "level", "unlock_value": "4"},
            ]
        )
    )
    cat = coord._settings["avatar_catalog"]
    assert len(cat) == 1
    assert cat[0]["icon"] == "mdi:star"
    assert cat[0]["unlock_value"] == 4


class TestAvatarPickerOnEveryDesign:
    """The avatar picker was wired into the classic child-card only.

    `render()` (classic) makes the avatar clickable and renders
    `_renderAvatarPicker`. `_renderDesigned` builds its header with `_av(...)`,
    a plain non-interactive element, and never opens the picker — so on
    playroom / console / cleanpro / accessible, tapping the avatar does
    nothing even though the same feature works on classic.
    """

    import pathlib as _pathlib

    SOURCE = (
        _pathlib.Path(__file__).resolve().parent.parent
        / "custom_components"
        / "taskmate"
        / "www"
        / "taskmate-child-card.js"
    ).read_text(encoding="utf-8")

    def _designed_region(self) -> str:
        start = self.SOURCE.index("_renderDesigned(design) {")
        end = self.SOURCE.index("\n  _designChoreMeta(", start)
        return self.SOURCE[start:end]

    def test_classic_opens_the_picker(self):
        classic = self.SOURCE[self.SOURCE.index("  render() {") : self.SOURCE.index("_renderDesigned(design) {")]
        assert "_toggleAvatarPicker()" in classic
        assert "_renderAvatarPicker(" in classic

    def test_designed_header_opens_the_picker(self):
        region = self._designed_region()
        assert "_toggleAvatarPicker()" in region, (
            "the designed header never wires the avatar to the picker, so it does nothing on any style but classic"
        )

    def test_designed_header_renders_the_picker(self):
        assert "_renderAvatarPicker(" in self._designed_region()
