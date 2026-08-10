"""Chore roulette (#677).

Opt-in nudge: spin once, get a random outstanding chore, earn a multiplier on
it. The pick is recorded per child per day so it survives a reload, can't be
re-rolled past the parent's allowance, and expires overnight.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.util import dt as dt_util

from custom_components.taskmate.models import Child, Chore

from .test_coordinator_logic import _make_coord


def _today():
    return dt_util.as_local(dt_util.now()).date().isoformat()


def _coord(*, enabled=True, multiplier=2.0, spins=1, chores=None, children=None, completions=None, available=True):
    settings = {
        "roulette_enabled": enabled,
        "roulette_multiplier": multiplier,
        "roulette_daily_spins": spins,
    }
    kids = children or [Child(name="Kid", id="kid1")]
    coord = _make_coord(settings=settings, children=kids, completions=completions or [])
    coord.storage.get_chores = MagicMock(return_value=list(chores or []))
    coord.storage.get_completions = MagicMock(return_value=list(completions or []))
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    coord.hass.bus.async_fire = MagicMock()
    coord.is_chore_available_for_child = MagicMock(return_value=available)

    # set_setting must actually persist so the spin result can be read back.
    def _set(key, value):
        settings[key] = value

    coord.storage.set_setting = MagicMock(side_effect=_set)
    coord.storage.get_setting = MagicMock(side_effect=lambda k, d="": settings.get(k, d))
    return coord


class TestSettings:
    def test_disabled_by_default(self):
        coord = _make_coord()
        assert coord.roulette_enabled() is False

    def test_multiplier_never_below_one(self):
        """A sub-1 multiplier would punish the child for spinning."""
        coord = _coord(multiplier=0.5)
        assert coord.roulette_multiplier() == 1.0

    def test_multiplier_falls_back_on_garbage(self):
        coord = _coord(multiplier="lots")
        assert coord.roulette_multiplier() == 2.0

    def test_spins_never_below_one(self):
        coord = _coord(spins=0)
        assert coord.roulette_daily_spins() == 1


class TestSpinning:
    @pytest.mark.asyncio
    async def test_spin_picks_an_available_chore(self):
        chores = [Chore(name="A", id="a"), Chore(name="B", id="b")]
        coord = _coord(chores=chores)
        result = await coord.async_spin_roulette("kid1")
        assert result["chore_id"] in {"a", "b"}
        assert result["multiplier"] == 2.0
        assert result["date"] == _today()
        coord.storage.async_save.assert_awaited()

    @pytest.mark.asyncio
    async def test_spin_refuses_when_disabled(self):
        coord = _coord(enabled=False, chores=[Chore(name="A", id="a")])
        with pytest.raises(ValueError, match="switched off"):
            await coord.async_spin_roulette("kid1")

    @pytest.mark.asyncio
    async def test_spin_refuses_unknown_child(self):
        coord = _coord(chores=[Chore(name="A", id="a")])
        coord.storage.get_child = MagicMock(return_value=None)
        with pytest.raises(ValueError, match="not found"):
            await coord.async_spin_roulette("nope")

    @pytest.mark.asyncio
    async def test_spin_refuses_with_nothing_to_pick(self):
        coord = _coord(chores=[])
        with pytest.raises(ValueError, match="Nothing left"):
            await coord.async_spin_roulette("kid1")

    @pytest.mark.asyncio
    async def test_unavailable_chores_are_never_picked(self):
        """Roulette must not hand a child a chore they aren't allowed to do."""
        coord = _coord(chores=[Chore(name="A", id="a")], available=False)
        with pytest.raises(ValueError, match="Nothing left"):
            await coord.async_spin_roulette("kid1")

    @pytest.mark.asyncio
    async def test_second_spin_refused_on_a_one_spin_allowance(self):
        coord = _coord(chores=[Chore(name="A", id="a")], spins=1)
        await coord.async_spin_roulette("kid1")
        with pytest.raises(ValueError, match="No spins left"):
            await coord.async_spin_roulette("kid1")

    @pytest.mark.asyncio
    async def test_allowance_of_two_permits_a_respin(self):
        coord = _coord(chores=[Chore(name="A", id="a"), Chore(name="B", id="b")], spins=2)
        first = await coord.async_spin_roulette("kid1")
        second = await coord.async_spin_roulette("kid1")
        assert second["spins"] == 2
        # A re-spin should move on rather than hand back the same chore.
        assert second["chore_id"] != first["chore_id"]

    @pytest.mark.asyncio
    async def test_respin_with_only_one_candidate_keeps_it(self):
        coord = _coord(chores=[Chore(name="A", id="a")], spins=2)
        await coord.async_spin_roulette("kid1")
        second = await coord.async_spin_roulette("kid1")
        assert second["chore_id"] == "a"

    @pytest.mark.asyncio
    async def test_spin_fires_an_event(self):
        coord = _coord(chores=[Chore(name="Tidy", id="a")])
        await coord.async_spin_roulette("kid1")
        event, payload = coord.hass.bus.async_fire.call_args[0]
        assert event == "taskmate_roulette_spun"
        assert payload["chore_name"] == "Tidy"
        assert payload["multiplier"] == 2.0

    @pytest.mark.asyncio
    async def test_completed_chores_are_not_candidates(self):
        completion = MagicMock()
        completion.chore_id = "a"
        completion.child_id = "kid1"
        completion.bonus_subtask_id = ""
        completion.completed_at = dt_util.now()
        coord = _coord(chores=[Chore(name="A", id="a")], completions=[completion])
        with pytest.raises(ValueError, match="Nothing left"):
            await coord.async_spin_roulette("kid1")


class TestSelectionLifetime:
    @pytest.mark.asyncio
    async def test_selection_readable_after_spinning(self):
        coord = _coord(chores=[Chore(name="A", id="a")])
        await coord.async_spin_roulette("kid1")
        assert coord.roulette_selection("kid1")["chore_id"] == "a"

    def test_no_selection_before_spinning(self):
        assert _coord().roulette_selection("kid1") is None

    def test_yesterdays_selection_is_ignored(self):
        """The pick is for today only — it must not linger into tomorrow."""
        yesterday = (dt_util.as_local(dt_util.now()).date() - timedelta(days=1)).isoformat()
        coord = _coord()
        coord.storage.set_setting(
            "roulette_state",
            {
                "kid1": {"date": yesterday, "chore_id": "a", "multiplier": 2.0, "spins": 1},
            },
        )
        assert coord.roulette_selection("kid1") is None
        assert coord.roulette_spins_left("kid1") == 1

    @pytest.mark.asyncio
    async def test_prune_clears_stale_days(self):
        yesterday = (dt_util.as_local(dt_util.now()).date() - timedelta(days=1)).isoformat()
        coord = _coord()
        coord.storage.set_setting(
            "roulette_state",
            {
                "kid1": {"date": yesterday, "chore_id": "a"},
                "kid2": {"date": _today(), "chore_id": "b"},
            },
        )
        assert await coord.async_prune_roulette_state() == 1
        remaining = coord.storage.get_setting("roulette_state", {})
        assert set(remaining) == {"kid2"}

    @pytest.mark.asyncio
    async def test_prune_is_a_no_op_when_all_current(self):
        coord = _coord()
        coord.storage.set_setting("roulette_state", {"kid1": {"date": _today(), "chore_id": "a"}})
        coord.storage.async_save.reset_mock()
        assert await coord.async_prune_roulette_state() == 0
        coord.storage.async_save.assert_not_awaited()


class TestMultiplier:
    @pytest.mark.asyncio
    async def test_multiplier_applies_to_the_picked_chore(self):
        chore = Chore(name="A", id="a")
        coord = _coord(chores=[chore])
        await coord.async_spin_roulette("kid1")
        assert coord._apply_roulette_multiplier(chore, "kid1", 10) == 20

    @pytest.mark.asyncio
    async def test_other_chores_are_unaffected(self):
        picked = Chore(name="A", id="a")
        other = Chore(name="B", id="b")
        coord = _coord(chores=[picked])
        await coord.async_spin_roulette("kid1")
        assert coord._apply_roulette_multiplier(other, "kid1", 10) == 10

    @pytest.mark.asyncio
    async def test_other_children_are_unaffected(self):
        """One child's spin must not inflate a sibling's award."""
        chore = Chore(name="A", id="a")
        coord = _coord(chores=[chore], children=[Child(name="Kid", id="kid1"), Child(name="Sib", id="kid2")])
        await coord.async_spin_roulette("kid1")
        assert coord._apply_roulette_multiplier(chore, "kid2", 10) == 10

    def test_no_selection_means_no_change(self):
        coord = _coord()
        assert coord._apply_roulette_multiplier(Chore(name="A", id="a"), "kid1", 10) == 10

    @pytest.mark.asyncio
    async def test_fractional_multiplier_rounds(self):
        chore = Chore(name="A", id="a")
        coord = _coord(chores=[chore], multiplier=1.5)
        await coord.async_spin_roulette("kid1")
        assert coord._apply_roulette_multiplier(chore, "kid1", 5) == 8  # 7.5 -> 8

    @pytest.mark.asyncio
    async def test_corrupt_stored_multiplier_falls_back(self):
        chore = Chore(name="A", id="a")
        coord = _coord(chores=[chore])
        with patch.object(
            coord.storage,
            "get_setting",
            side_effect=lambda k, d="": (
                {"kid1": {"date": _today(), "chore_id": "a", "multiplier": "loads", "spins": 1}}
                if k == "roulette_state"
                else {"roulette_enabled": True}.get(k, d)
            ),
        ):
            assert coord._apply_roulette_multiplier(chore, "kid1", 10) == 20


class TestRouletteRendersOnEveryDesign:
    """The spin button only ever rendered on the classic card.

    `_renderRoulette` was called once, from the classic branch of render().
    `_renderDesigned` returns before that branch is reached, so a family using
    playroom, console, cleanpro or accessible had `show_roulette: true` in
    their config and no button on screen — with nothing logged to explain it.
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
        # End at the *definition* of the next method, not the call to it that
        # appears inside this one.
        end = self.SOURCE.index("\n  _designHeaderFull(", start)
        return self.SOURCE[start:end]

    def _classic_region(self) -> str:
        start = self.SOURCE.index("  render() {")
        end = self.SOURCE.index("_renderDesigned(design) {")
        return self.SOURCE[start:end]

    def test_classic_renders_the_roulette(self):
        assert "this._renderRoulette(" in self._classic_region()

    def test_designed_styles_render_the_roulette(self):
        assert "this._renderRoulette(" in self._designed_region(), (
            "the designed render path never calls _renderRoulette, so the spin "
            "button is invisible on playroom / console / cleanpro / accessible"
        )

    def test_roulette_styling_follows_the_active_design(self):
        """Hard-coded purple ignores the design tokens, so the button looked
        pasted-on under every style but classic."""
        import re

        block = re.search(r"\.roulette-btn \{([^}]*)\}", self.SOURCE)
        assert block, "could not find the .roulette-btn rule"
        assert "var(--tmd-" in block.group(1)
