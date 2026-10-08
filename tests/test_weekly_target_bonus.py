"""Weekly target bonus: extra points for filling a chore's weekly quota (#1044).

A chore with ``weekly_target`` can carry a ``weekly_target_bonus``. Once the
child's *approved* completions for the week reach the target, the bonus is paid
as its own transaction — once per chore, child and Monday-anchored week. If an
undo or rejection drops the week back below the target, the bonus is refunded.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion

UTC = dt.timezone.utc
NOW = dt.datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)  # Wednesday
MONDAY = dt.datetime(2026, 4, 20, 9, 0, 0, tzinfo=UTC)
TUESDAY = dt.datetime(2026, 4, 21, 9, 0, 0, tzinfo=UTC)
LAST_SUNDAY = dt.datetime(2026, 4, 19, 9, 0, 0, tzinfo=UTC)
WWW = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _comp(when, *, approved=True, cid=None, bonus_subtask_id=""):
    kwargs = {"id": cid} if cid else {}
    return ChoreCompletion(
        chore_id="a",
        child_id="c1",
        completed_at=when,
        approved=approved,
        points_awarded=5 if approved else 0,
        bonus_subtask_id=bonus_subtask_id,
        **kwargs,
    )


def _coord(chore, completions, child=None):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.data = {}
    coord.hass.bus = MagicMock()
    bonuses: dict = {}
    storage = MagicMock()
    storage.get_completions = MagicMock(return_value=completions)
    storage.get_weekly_target_bonus = MagicMock(side_effect=lambda ch, c: bonuses.get(f"{ch}:{c}", {}))

    def _set(ch, c, record):
        if record is None:
            bonuses.pop(f"{ch}:{c}", None)
        else:
            bonuses[f"{ch}:{c}"] = record

    storage.set_weekly_target_bonus = MagicMock(side_effect=_set)
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord._bonuses = bonuses
    coord.get_child = MagicMock(return_value=child)
    coord.get_chore = MagicMock(return_value=chore)
    coord.async_refresh = AsyncMock()
    coord._maybe_level_up = AsyncMock()
    coord._celebrate = AsyncMock()
    return coord


def _child():
    return Child(name="Mia", id="c1", points=100, total_points_earned=200)


def _pay(coord, chore, child, completion):
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        run(coord._async_pay_weekly_target_bonus(chore, child, completion))


def _transactions(coord):
    return [c.args[0] for c in coord.storage.add_points_transaction.call_args_list]


def _fired(coord, name):
    return [c for c in coord.hass.bus.async_fire.call_args_list if c[0][0] == name]


# ── the field ────────────────────────────────────────────────────────────────


def test_weekly_target_bonus_defaults_to_zero():
    assert Chore(name="Teeth", id="a").weekly_target_bonus == 0


def test_weekly_target_bonus_round_trips_through_storage():
    chore = Chore(name="Teeth", id="a", weekly_target=7, weekly_target_bonus=10)
    assert Chore.from_dict(chore.to_dict()).weekly_target_bonus == 10


def test_negative_stored_bonus_loads_as_zero():
    assert Chore.from_dict({"name": "Teeth", "weekly_target_bonus": -5}).weekly_target_bonus == 0


# ── paying it ────────────────────────────────────────────────────────────────


def test_bonus_paid_when_the_target_is_reached():
    chore = Chore(name="Teeth", id="a", weekly_target=2, weekly_target_bonus=10)
    comps = [_comp(MONDAY), _comp(TUESDAY)]
    child = _child()
    coord = _coord(chore, comps, child)
    _pay(coord, chore, child, comps[-1])
    assert child.points == 110
    assert child.total_points_earned == 210
    (txn,) = _transactions(coord)
    assert txn.points == 10
    assert txn.reason == "Weekly target bonus: Teeth"
    assert len(_fired(coord, "taskmate_weekly_target_reached")) == 1
    coord._celebrate.assert_awaited_once()
    assert coord._celebrate.call_args.args[1] == "weekly_target_reached"


def test_no_bonus_below_the_target():
    chore = Chore(name="Teeth", id="a", weekly_target=3, weekly_target_bonus=10)
    comps = [_comp(MONDAY), _comp(TUESDAY)]
    child = _child()
    coord = _coord(chore, comps, child)
    _pay(coord, chore, child, comps[-1])
    assert child.points == 100
    coord.storage.add_points_transaction.assert_not_called()


def test_no_bonus_when_none_is_configured():
    chore = Chore(name="Teeth", id="a", weekly_target=2, weekly_target_bonus=0)
    comps = [_comp(MONDAY), _comp(TUESDAY)]
    child = _child()
    coord = _coord(chore, comps, child)
    _pay(coord, chore, child, comps[-1])
    assert child.points == 100
    coord._celebrate.assert_not_awaited()


def test_pending_completions_do_not_earn_the_bonus():
    # The quota counts pending work, but points are only paid on approval.
    chore = Chore(name="Teeth", id="a", weekly_target=2, weekly_target_bonus=10)
    comps = [_comp(MONDAY), _comp(TUESDAY, approved=False)]
    child = _child()
    coord = _coord(chore, comps, child)
    _pay(coord, chore, child, comps[0])
    assert child.points == 100


def test_bonus_subtasks_do_not_count_towards_it():
    chore = Chore(name="Teeth", id="a", weekly_target=2, weekly_target_bonus=10)
    comps = [_comp(MONDAY), _comp(MONDAY, bonus_subtask_id="bs1")]
    child = _child()
    coord = _coord(chore, comps, child)
    _pay(coord, chore, child, comps[0])
    assert child.points == 100


def test_bonus_paid_only_once_a_week():
    chore = Chore(name="Teeth", id="a", weekly_target=2, weekly_target_bonus=10)
    comps = [_comp(MONDAY), _comp(TUESDAY), _comp(NOW)]
    child = _child()
    coord = _coord(chore, comps, child)
    _pay(coord, chore, child, comps[1])
    _pay(coord, chore, child, comps[2])
    assert child.points == 110
    assert len(_transactions(coord)) == 1


def test_last_weeks_late_approval_settles_last_week_only():
    # Approving last Sunday's work on Wednesday pays last week's bonus and
    # leaves this week's still to be earned.
    chore = Chore(name="Teeth", id="a", weekly_target=1, weekly_target_bonus=10)
    last_week = _comp(LAST_SUNDAY)
    this_week = _comp(MONDAY)
    child = _child()
    coord = _coord(chore, [last_week, this_week], child)
    _pay(coord, chore, child, last_week)
    _pay(coord, chore, child, this_week)
    assert child.points == 120
    assert set(coord._bonuses["a:c1"]) == {"2026-04-13", "2026-04-20"}


def test_auto_approved_completion_pays_the_bonus():
    chore = Chore(name="Teeth", id="a", weekly_target=2, weekly_target_bonus=10, daily_limit=5, requires_approval=False)
    comps = [_comp(MONDAY)]
    child = _child()
    coord = _coord(chore, comps, child)
    coord.storage.get_chore = MagicMock(return_value=chore)
    coord.storage.get_chores = MagicMock(return_value=[chore])
    coord.storage.add_completion = MagicMock(side_effect=comps.append)
    coord._is_chore_completable_by_child = MagicMock(return_value=True)
    coord.is_chore_available_for_child = MagicMock(return_value=True)
    coord._compute_active_children = MagicMock(return_value=["c1"])
    coord._is_rotation_done_today = MagicMock(return_value=False)
    coord.effective_chore_points = MagicMock(return_value=5)
    coord._apply_time_adjustment = MagicMock(side_effect=lambda c, b, t: b)
    coord._award_points = AsyncMock(return_value=5)
    coord.badges = None
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        run(coord.async_complete_chore("a", "c1"))
    assert child.points == 110
    assert [t.reason for t in _transactions(coord)] == ["Weekly target bonus: Teeth"]


# ── taking it back ───────────────────────────────────────────────────────────


def test_undoing_an_approval_below_the_target_refunds_the_bonus():
    chore = Chore(name="Teeth", id="a", weekly_target=2, weekly_target_bonus=10)
    comps = [_comp(MONDAY, cid="m"), _comp(TUESDAY, cid="t")]
    child = _child()
    coord = _coord(chore, comps, child)
    _pay(coord, chore, child, comps[1])
    assert child.points == 110
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        run(coord.async_undo_chore_approval("t"))
    # The completion's own 5 points and the 10-point bonus both come back off.
    assert child.points == 95
    assert child.total_points_earned == 195
    assert _transactions(coord)[-1].points == -10
    assert _transactions(coord)[-1].reason.startswith("Weekly target bonus reversed")
    assert "a:c1" not in coord._bonuses


def test_bonus_can_be_earned_again_after_a_refund():
    chore = Chore(name="Teeth", id="a", weekly_target=2, weekly_target_bonus=10)
    comps = [_comp(MONDAY, cid="m"), _comp(TUESDAY, cid="t")]
    child = _child()
    coord = _coord(chore, comps, child)
    _pay(coord, chore, child, comps[1])
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        run(coord.async_undo_chore_approval("t"))
    comps[1].approved = True
    _pay(coord, chore, child, comps[1])
    assert len([t for t in _transactions(coord) if t.points == 10]) == 2


def test_undo_that_leaves_the_target_met_keeps_the_bonus():
    # The target was lowered after the bonus was paid: three approved, target
    # two, so undoing one still leaves the week's quota filled.
    chore = Chore(name="Teeth", id="a", weekly_target=2, weekly_target_bonus=10)
    comps = [_comp(MONDAY, cid="m"), _comp(TUESDAY, cid="t"), _comp(NOW, cid="w")]
    child = _child()
    coord = _coord(chore, comps, child)
    _pay(coord, chore, child, comps[1])
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        run(coord.async_undo_chore_approval("w"))
    assert child.points == 105  # only the completion's own 5 points
    assert "a:c1" in coord._bonuses


def test_rejecting_a_paid_completion_refunds_the_bonus():
    chore = Chore(name="Teeth", id="a", weekly_target=2, weekly_target_bonus=10)
    comps = [_comp(MONDAY, cid="m"), _comp(TUESDAY, cid="t")]
    child = _child()
    coord = _coord(chore, comps, child)
    _pay(coord, chore, child, comps[1])
    coord.notifications = MagicMock()
    coord.notifications.clear_approval = AsyncMock()
    coord._async_notify_rejected = AsyncMock()
    coord.async_recheck_mandatory_miss = AsyncMock()
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        run(coord.async_reject_chore("m"))
    assert child.points == 95
    assert "a:c1" not in coord._bonuses


def test_undo_from_another_week_leaves_this_weeks_bonus_alone():
    chore = Chore(name="Teeth", id="a", weekly_target=1, weekly_target_bonus=10)
    last_week = _comp(LAST_SUNDAY, cid="s")
    this_week = _comp(MONDAY, cid="m")
    child = _child()
    coord = _coord(chore, [last_week, this_week], child)
    _pay(coord, chore, child, this_week)
    with patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW):
        run(coord.async_undo_chore_approval("s"))
    assert child.points == 105
    assert "2026-04-20" in coord._bonuses["a:c1"]


def test_bonus_transactions_cannot_be_undone_on_their_own():
    # Reversing the row alone would leave the week marked as paid.
    from custom_components.taskmate.coord_points import PointsMixin

    assert "Weekly target bonus: Teeth".startswith(PointsMixin._UNDO_DENY_PREFIXES)
    assert "Weekly target bonus reversed: Teeth".startswith(PointsMixin._UNDO_DENY_PREFIXES)


# ── surfaces ─────────────────────────────────────────────────────────────────


def test_weekly_target_bonus_is_editable_over_the_websocket():
    from custom_components.taskmate.websocket import _CHORE_EDITABLE_FIELDS, _chore_payload_schema

    assert "weekly_target_bonus" in _CHORE_EDITABLE_FIELDS
    schema = vol.Schema(_chore_payload_schema(require_name=False))
    assert schema({"weekly_target_bonus": 10})["weekly_target_bonus"] == 10
    with pytest.raises(vol.Invalid):
        schema({"weekly_target_bonus": -1})


def _record(chore):
    coord = object.__new__(TaskMateCoordinator)
    coord.storage = MagicMock()
    coord.storage.get_completions = MagicMock(return_value=[])
    coord.effective_chore_points = MagicMock(side_effect=lambda c: c.points)
    return sensor_module._build_chores_list(coord, {"chores": [chore]})[0]


def test_chores_slice_carries_the_bonus_for_the_child_card():
    record = _record(Chore(name="Teeth", id="a", weekly_target=7, weekly_target_bonus=10))
    assert record["weekly_target_bonus"] == 10


def test_chores_slice_omits_the_bonus_when_unused():
    assert "weekly_target_bonus" not in _record(Chore(name="Teeth", id="a", weekly_target=7))
    # A bonus without a target never pays, so it isn't worth the bytes either.
    assert "weekly_target_bonus" not in _record(Chore(name="Teeth", id="a", weekly_target_bonus=10))


def test_panel_seeds_and_sends_the_bonus():
    panel = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")
    assert "weekly_target_bonus: 0" in panel
    assert "weekly_target_bonus: Math.max(0, Number(d.weekly_target_bonus)" in panel
    assert "panel.chore_weekly_target_bonus_label" in panel


@pytest.mark.parametrize("locale", ["en", "en-GB", "da", "de", "fr", "nb", "nn", "pl", "pt", "pt-BR"])
@pytest.mark.parametrize(
    "key",
    [
        "panel.chore_weekly_target_bonus_label",
        "panel.chore_weekly_target_bonus_hint",
        "child.weekly_target_bonus_reached",
        "notify.celebrate_weekly_target",
    ],
)
def test_new_strings_are_translated_everywhere(locale, key):
    strings = json.loads((WWW / "locales" / f"{locale}.json").read_text(encoding="utf-8"))
    assert strings.get(key, "").strip(), f"{key} missing from {locale}.json"


# ── storage ──────────────────────────────────────────────────────────────────


def _storage():
    from custom_components.taskmate.storage import TaskMateStorage

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage._data = {}
    return storage


def test_storage_records_and_forgets_a_paid_bonus():
    storage = _storage()
    storage.set_weekly_target_bonus("a", "c1", {"2026-04-20": 10})
    assert storage.get_weekly_target_bonus("a", "c1") == {"2026-04-20": 10}
    storage.set_weekly_target_bonus("a", "c1", None)
    assert storage.get_weekly_target_bonus("a", "c1") == {}


def test_removing_a_chore_or_child_drops_its_bonus_records():
    storage = _storage()
    for key in (("a", "c1"), ("a", "c2"), ("b", "c1"), ("b", "c2")):
        storage.set_weekly_target_bonus(*key, {"2026-04-20": 10})
    storage.remove_weekly_target_bonuses(chore_id="a")
    storage.remove_weekly_target_bonuses(child_id="c2")
    assert storage._data["weekly_target_bonuses"] == {"b:c1": {"2026-04-20": 10}}


def test_a_corrupt_bonus_store_reads_as_empty():
    storage = _storage()
    storage._data["weekly_target_bonuses"] = ["not", "a", "dict"]
    assert storage.get_weekly_target_bonus("a", "c1") == {}
