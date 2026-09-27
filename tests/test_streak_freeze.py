"""Streak freeze tokens (#925): a child-owned token that saves a streak on a missed day.

- The midnight streak check spends one token per missed day while they last,
  instead of resetting/pausing the streak. The next completion then continues
  the streak across the covered gap.
- A day that is already forgiven — a vacation day, the child being away, a
  streak already paused, or no streak at all — never costs a token.
- Tokens are earned every ``streak_freeze_earn_every`` streak days, bought via
  a fixed-cost "Streak freeze" reward, and granted/removed by a parent through
  ``adjust_streak_freezes``. All three respect ``streak_freeze_max``.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import pathlib
import re
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import custom_components.taskmate.coord_points as coord_points_mod
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Reward
from custom_components.taskmate.sensor import _build_children_summary, _build_rewards_list
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc
WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"

# Midnight check on Thursday 2026-07-16: "yesterday" is Wednesday the 15th.
MIDNIGHT = dt.datetime(2026, 7, 16, 0, 0, 5, tzinfo=UTC)


def _run(coro_factory):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


async def _make_system(settings: dict | None = None):
    from tests.conftest import FakeHass, FakeStore

    hass = FakeHass()
    hass.states = type("FakeStates", (), {"get": lambda self, entity_id: None})()

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {}
    await storage.async_load()
    for key, value in (settings or {}).items():
        storage.set_setting(key, value)

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.data = {}
    coord.storage = storage
    coord._unsub_midnight = None
    coord._unsub_prune = None
    coord._unsub_availability = None
    coord.async_refresh = AsyncMock()
    coord.notifications = AsyncMock()
    coord._celebrate = AsyncMock()
    return coord


async def _kid(coord, *, streak=5, last="2026-07-14", freezes=0, **extra):
    child = await coord.async_add_child("Mia")
    child.current_streak = streak
    child.best_streak = max(streak, child.best_streak)
    child.last_completion_date = last
    child.streak_freezes = freezes
    for key, value in extra.items():
        setattr(child, key, value)
    coord.storage.update_child(child)
    return child


async def _check(coord, now=MIDNIGHT):
    with patch.object(coord_points_mod.dt_util, "now", return_value=now):
        await coord._async_check_streaks()


def _reasons(coord, child_id):
    return [t.reason for t in coord.storage.get_points_transactions() if t.child_id == child_id]


# ── the midnight check spends tokens ─────────────────────────────────────


def test_a_missed_day_spends_a_token_and_keeps_the_streak():
    async def scenario():
        coord = await _make_system()
        child = await _kid(coord, freezes=1)
        await _check(coord)
        kid = coord.storage.get_child(child.id)
        assert kid.current_streak == 5
        assert kid.streak_paused is False
        assert kid.streak_freezes == 0
        assert kid.streak_freeze_dates == ["2026-07-15"]
        assert "Streak freeze used (2026-07-15)" in _reasons(coord, child.id)
        coord.notifications.fire.assert_awaited_once()
        type_id, ctx = coord.notifications.fire.await_args.args
        assert type_id == "streak_freeze_used"
        assert ctx["child_name"] == "Mia" and ctx["freezes_left"] == 0 and ctx["streak"] == 5
        fired = [c.args[0] for c in coord.hass.bus.async_fire.call_args_list]
        assert "taskmate_streak_freeze_used" in fired

    _run(scenario)


def test_the_next_completion_continues_across_the_covered_day():
    async def scenario():
        coord = await _make_system()
        child = await _kid(coord, freezes=1)
        await _check(coord)
        kid = coord.storage.get_child(child.id)
        with patch.object(coord_points_mod.dt_util, "now", return_value=MIDNIGHT.replace(hour=12)):
            await coord._award_points(kid, 5)
        assert kid.current_streak == 6
        assert kid.last_completion_date == "2026-07-16"

    _run(scenario)


def test_the_check_is_idempotent_once_the_day_is_covered():
    async def scenario():
        coord = await _make_system()
        child = await _kid(coord, freezes=2)
        await _check(coord)
        await _check(coord)
        assert coord.storage.get_child(child.id).streak_freezes == 1

    _run(scenario)


def test_each_missed_day_costs_one_token():
    async def scenario():
        coord = await _make_system()
        # Last completed Sunday the 12th: Mon, Tue and Wed were all missed.
        child = await _kid(coord, last="2026-07-12", freezes=3)
        await _check(coord)
        kid = coord.storage.get_child(child.id)
        assert kid.current_streak == 5
        assert kid.streak_freezes == 0
        assert kid.streak_freeze_dates == ["2026-07-13", "2026-07-14", "2026-07-15"]

    _run(scenario)


def test_running_out_of_tokens_still_breaks_the_streak():
    async def scenario():
        coord = await _make_system({"streak_reset_mode": "reset"})
        child = await _kid(coord, last="2026-07-13", freezes=1)
        await _check(coord)
        kid = coord.storage.get_child(child.id)
        assert kid.streak_freezes == 0
        assert kid.current_streak == 0

    _run(scenario)


def test_pause_mode_spends_the_token_instead_of_pausing():
    async def scenario():
        coord = await _make_system({"streak_reset_mode": "pause"})
        child = await _kid(coord, freezes=1)
        await _check(coord)
        kid = coord.storage.get_child(child.id)
        assert kid.streak_freezes == 0
        assert kid.streak_paused is False
        assert kid.current_streak == 5

    _run(scenario)


def test_no_tokens_keeps_the_old_behaviour():
    async def scenario():
        coord = await _make_system()
        child = await _kid(coord, freezes=0)
        await _check(coord)
        assert coord.storage.get_child(child.id).current_streak == 0
        coord.notifications.fire.assert_not_awaited()

    _run(scenario)


# ── days that are already forgiven never cost a token ────────────────────


def test_a_vacation_day_does_not_cost_a_token():
    async def scenario():
        coord = await _make_system(
            {"vacation_periods": [{"id": "v", "name": "Trip", "start": "2026-07-15", "end": "2026-07-15"}]}
        )
        child = await _kid(coord, freezes=1)
        await _check(coord)
        kid = coord.storage.get_child(child.id)
        assert kid.streak_freezes == 1
        assert kid.current_streak == 5

    _run(scenario)


def test_a_gap_mixing_vacation_and_a_missed_day_costs_only_the_missed_day():
    async def scenario():
        coord = await _make_system(
            {"vacation_periods": [{"id": "v", "name": "Trip", "start": "2026-07-13", "end": "2026-07-14"}]}
        )
        child = await _kid(coord, last="2026-07-12", freezes=2)
        await _check(coord)
        kid = coord.storage.get_child(child.id)
        assert kid.streak_freezes == 1
        assert kid.streak_freeze_dates == ["2026-07-15"]
        # And the next completion carries the streak across vacation + token.
        with patch.object(coord_points_mod.dt_util, "now", return_value=MIDNIGHT.replace(hour=12)):
            await coord._award_points(kid, 5)
        assert kid.current_streak == 6

    _run(scenario)


def test_a_child_away_today_does_not_spend_a_token():
    async def scenario():
        coord = await _make_system()
        child = await _kid(coord, freezes=1)
        with patch.object(TaskMateCoordinator, "_is_child_on_vacation", return_value=True):
            await _check(coord)
        kid = coord.storage.get_child(child.id)
        assert kid.streak_freezes == 1
        assert kid.streak_paused is True

    _run(scenario)


def test_an_already_paused_streak_does_not_spend_a_token():
    async def scenario():
        coord = await _make_system()
        # Paused by an earlier absence: it resumes on its own, nothing at risk.
        child = await _kid(coord, freezes=1, streak_paused=True)
        await _check(coord)
        kid = coord.storage.get_child(child.id)
        assert kid.streak_freezes == 1
        assert kid.current_streak == 5

    _run(scenario)


def test_no_streak_means_no_token_spent():
    async def scenario():
        coord = await _make_system()
        child = await _kid(coord, streak=0, freezes=1)
        await _check(coord)
        assert coord.storage.get_child(child.id).streak_freezes == 1

    _run(scenario)


def test_feature_off_never_spends_tokens():
    async def scenario():
        coord = await _make_system({"streak_freeze_max": 0})
        child = await _kid(coord, freezes=2)
        await _check(coord)
        kid = coord.storage.get_child(child.id)
        assert kid.streak_freezes == 2
        assert kid.current_streak == 0

    _run(scenario)


# ── earning ──────────────────────────────────────────────────────────────


def test_a_token_is_earned_on_every_nth_streak_day():
    async def scenario():
        coord = await _make_system({"streak_freeze_earn_every": 7})
        child = await _kid(coord, streak=6, last="2026-07-15")
        with patch.object(coord_points_mod.dt_util, "now", return_value=MIDNIGHT.replace(hour=12)):
            await coord._award_points(child, 5)
        assert child.current_streak == 7
        assert child.streak_freezes == 1
        assert child.streak_freeze_earned_at == 7
        assert "Streak freeze earned (7 day streak!)" in _reasons(coord, child.id)

    _run(scenario)


def test_earning_stops_at_the_cap():
    async def scenario():
        coord = await _make_system({"streak_freeze_earn_every": 7, "streak_freeze_max": 2})
        child = await _kid(coord, streak=6, last="2026-07-15", freezes=2)
        with patch.object(coord_points_mod.dt_util, "now", return_value=MIDNIGHT.replace(hour=12)):
            await coord._award_points(child, 5)
        assert child.streak_freezes == 2
        assert child.streak_freeze_earned_at == 0

    _run(scenario)


def test_earning_off_when_earn_every_is_zero():
    async def scenario():
        coord = await _make_system({"streak_freeze_earn_every": 0})
        child = await _kid(coord, streak=6, last="2026-07-15")
        with patch.object(coord_points_mod.dt_util, "now", return_value=MIDNIGHT.replace(hour=12)):
            await coord._award_points(child, 5)
        assert child.streak_freezes == 0

    _run(scenario)


def test_a_second_completion_the_same_day_does_not_earn_again():
    async def scenario():
        coord = await _make_system({"streak_freeze_earn_every": 7})
        child = await _kid(coord, streak=6, last="2026-07-15")
        with patch.object(coord_points_mod.dt_util, "now", return_value=MIDNIGHT.replace(hour=12)):
            await coord._award_points(child, 5)
            await coord._award_points(child, 5)
        assert child.streak_freezes == 1

    _run(scenario)


def test_undoing_the_earning_completion_takes_the_token_back():
    async def scenario():
        coord = await _make_system()
        child = await _kid(coord, streak=6, freezes=1, streak_freeze_earned_at=0)
        child.current_streak = 7
        child.streak_freezes = 2
        child.streak_freeze_earned_at = 7
        # _reverse_completion_awards drops the streak by one and then asks.
        child.current_streak = 6
        coord._reverse_streak_freeze_earn(child, 7)
        assert child.streak_freezes == 1
        assert child.streak_freeze_earned_at == 0
        assert "Streak freeze reversed" in _reasons(coord, child.id)
        # A second undo further down the streak takes nothing more.
        child.current_streak = 5
        coord._reverse_streak_freeze_earn(child, 6)
        assert child.streak_freezes == 1

    _run(scenario)


# ── parent adjustments ───────────────────────────────────────────────────


def test_parent_grant_respects_the_cap():
    async def scenario():
        coord = await _make_system({"streak_freeze_max": 2})
        child = await _kid(coord, freezes=1)
        assert await coord.async_adjust_streak_freezes(child.id, 5) == 2
        assert "Streak freezes adjusted (+1)" in _reasons(coord, child.id)
        with pytest.raises(ValueError, match="maximum"):
            await coord.async_adjust_streak_freezes(child.id, 1)

    _run(scenario)


def test_parent_removal_floors_at_zero():
    async def scenario():
        coord = await _make_system()
        child = await _kid(coord, freezes=1)
        assert await coord.async_adjust_streak_freezes(child.id, -3) == 0
        assert "Streak freezes adjusted (-1)" in _reasons(coord, child.id)
        # Nothing left to take: a no-op, not an error, and nothing logged.
        assert await coord.async_adjust_streak_freezes(child.id, -1) == 0
        assert _reasons(coord, child.id).count("Streak freezes adjusted (-1)") == 1

    _run(scenario)


def test_parent_grant_refused_when_feature_off():
    async def scenario():
        coord = await _make_system({"streak_freeze_max": 0})
        child = await _kid(coord)
        with pytest.raises(ValueError, match="turned off"):
            await coord.async_adjust_streak_freezes(child.id, 1)

    _run(scenario)


def test_parent_adjust_unknown_child():
    async def scenario():
        coord = await _make_system()
        with pytest.raises(ValueError, match="not found"):
            await coord.async_adjust_streak_freezes("ghost", 1)

    _run(scenario)


# ── the Streak freeze reward ─────────────────────────────────────────────


async def _freeze_reward(coord, cost=30):
    reward = Reward(name="Streak freeze", cost=cost, streak_freeze=True)
    coord.storage.add_reward(reward)
    return reward


def test_buying_a_streak_freeze_charges_the_fixed_cost_and_grants_a_token():
    async def scenario():
        coord = await _make_system()
        child = await _kid(coord, points=100)
        child.points = 100
        coord.storage.update_child(child)
        reward = await _freeze_reward(coord, cost=30)
        claim = await coord.async_claim_reward(reward.id, child.id)
        await coord.async_approve_reward(claim.id)
        kid = coord.storage.get_child(child.id)
        assert kid.points == 70
        assert kid.streak_freezes == 1

    _run(scenario)


def test_cannot_claim_a_streak_freeze_at_the_cap():
    async def scenario():
        coord = await _make_system({"streak_freeze_max": 2})
        child = await _kid(coord, freezes=2)
        child.points = 100
        coord.storage.update_child(child)
        reward = await _freeze_reward(coord)
        with pytest.raises(ValueError, match="maximum"):
            coord.validate_reward_claim(reward.id, child.id)

    _run(scenario)


def test_pending_freeze_claims_count_toward_the_cap():
    async def scenario():
        coord = await _make_system({"streak_freeze_max": 1})
        child = await _kid(coord, freezes=0)
        child.points = 100
        coord.storage.update_child(child)
        first = await _freeze_reward(coord)
        second = Reward(name="Another freeze", cost=10, streak_freeze=True)
        coord.storage.add_reward(second)
        await coord.async_claim_reward(first.id, child.id)
        with pytest.raises(ValueError, match="maximum"):
            coord.validate_reward_claim(second.id, child.id)

    _run(scenario)


def test_approval_rechecks_the_cap():
    async def scenario():
        coord = await _make_system({"streak_freeze_max": 1})
        child = await _kid(coord, freezes=0)
        child.points = 100
        coord.storage.update_child(child)
        reward = await _freeze_reward(coord)
        claim = await coord.async_claim_reward(reward.id, child.id)
        # Earned one while the claim sat in the queue.
        kid = coord.storage.get_child(child.id)
        kid.streak_freezes = 1
        coord.storage.update_child(kid)
        with pytest.raises(ValueError, match="maximum"):
            await coord.async_approve_reward(claim.id)
        assert coord.storage.get_child(child.id).points == 100

    _run(scenario)


def test_claiming_refused_when_feature_off():
    async def scenario():
        coord = await _make_system({"streak_freeze_max": 0})
        child = await _kid(coord)
        child.points = 100
        coord.storage.update_child(child)
        reward = await _freeze_reward(coord)
        with pytest.raises(ValueError, match="turned off"):
            coord.validate_reward_claim(reward.id, child.id)

    _run(scenario)


def test_a_streak_freeze_reward_is_never_a_jackpot():
    reward = Reward(name="Freeze", cost=10, streak_freeze=True, is_jackpot=True)
    assert reward.is_jackpot is False

    async def scenario():
        coord = await _make_system()
        stored = await _freeze_reward(coord)
        stored.is_jackpot = True
        await coord.async_update_reward(stored)
        assert coord.get_reward(stored.id).is_jackpot is False

    _run(scenario)


# ── models / storage ─────────────────────────────────────────────────────


def test_old_records_load_with_safe_defaults():
    child = Child.from_dict({"name": "Old", "id": "c1"})
    assert child.streak_freezes == 0
    assert child.streak_freeze_dates == []
    assert child.streak_freeze_earned_at == 0
    assert Reward.from_dict({"name": "Old", "id": "r1"}).streak_freeze is False


def test_fields_round_trip():
    child = Child(name="A", streak_freezes=2, streak_freeze_dates=["2026-07-15"], streak_freeze_earned_at=14)
    again = Child.from_dict(child.to_dict())
    assert (again.streak_freezes, again.streak_freeze_dates, again.streak_freeze_earned_at) == (
        2,
        ["2026-07-15"],
        14,
    )
    assert Reward.from_dict(Reward(name="F", streak_freeze=True).to_dict()).streak_freeze is True


def test_covered_days_list_stays_bounded():
    async def scenario():
        coord = await _make_system({"streak_freeze_max": 10})
        old = [f"2026-06-{d:02d}" for d in range(1, 31)] + ["2026-07-01", "2026-07-02"]
        child = await _kid(coord, freezes=1, streak_freeze_dates=old)
        await _check(coord)
        dates = coord.storage.get_child(child.id).streak_freeze_dates
        assert len(dates) == 31
        assert dates[-1] == "2026-07-15"

    _run(scenario)


# ── sensors ──────────────────────────────────────────────────────────────


def _summary(settings: dict, child: Child):
    coord = MagicMock()
    coord.level_info = MagicMock(return_value={"level": 1, "progress": 0, "target": 100})
    coord.roulette_enabled = MagicMock(return_value=False)
    coord._is_child_on_vacation = MagicMock(return_value=False)
    coord.quest_progress_for_child = MagicMock(return_value=[])
    coord.avatar_options_for_child = MagicMock(return_value=[])
    coord.challenge_progress_for_child = MagicMock(return_value=[])
    common = {
        "data": {"settings": settings},
        "children": [child],
        "chores": [],
        "pending_points_by_child": {},
        "committed_points_by_child": {},
        "total_allocated_by_child": {},
        "season_points": {},
    }
    return _build_children_summary(coord, common)[0]


def test_child_summary_carries_tokens_only_while_the_feature_is_on():
    child = Child(name="A", id="c1", streak_freezes=2)
    assert _summary({}, child)["streak_freezes"] == 2
    assert _summary({"streak_freeze_max": 0}, child).get("streak_freezes") is None


def test_rewards_list_flags_only_streak_freeze_rewards():
    plain = Reward(name="Ice cream", cost=10, id="r1")
    freeze = Reward(name="Freeze", cost=20, id="r2", streak_freeze=True)
    common = {
        "rewards": [plain, freeze],
        "children": [],
        "pool_by_child_reward": {},
        "pool_total_by_reward": {},
    }
    out = {r["id"]: r for r in _build_rewards_list(common)}
    assert "streak_freeze" not in out["r1"]
    assert out["r2"]["streak_freeze"] is True
    assert out["r2"]["cost"] == 20


# ── cards: every render path shows the token count ───────────────────────


def _method_body(src: str, name: str) -> str:
    m = re.search(rf"\n  {name}\([^)]*\) \{{(.*?)\n  \}}", src, re.S)
    assert m, f"could not find {name}"
    return m.group(1)


def test_streak_card_shows_tokens_in_every_layout():
    src = (WWW / "taskmate-streak-card.js").read_text(encoding="utf-8")
    for method in ("_renderStreakTile", "_skPlayroom", "_skConsole", "_skCleanpro"):
        assert "_freezeChip(" in _method_body(src, method), f"{method} does not render the streak-freeze chip"


def test_child_card_shows_tokens_on_both_render_paths():
    src = (WWW / "taskmate-child-card.js").read_text(encoding="utf-8")
    classic = src[src.index("  render() {") : src.index("  _renderDesigned(design) {")]
    assert "_renderFreezeBadge(" in classic
    assert "_renderFreezeBadge(" in _method_body(src, "_designHeaderFull")
