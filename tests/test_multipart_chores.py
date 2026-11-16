"""Multipart chores (#1253): a chore with required steps.

The child ticks the steps off one by one; ticking earns nothing. The chore is
completed through the ordinary ``async_complete_chore`` path, which refuses a
child's completion while a step is still open, so points arrive only once
every step is done. Ticks are kept per child and per day, and a chore done
more than once a day starts each go with a clean checklist.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
from datetime import timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.errors import TaskMateError
from custom_components.taskmate.models import (
    MAX_CHORE_STEPS,
    Child,
    Chore,
    ChoreStep,
    ChoreTime,
    clean_chore_steps,
    validate_chore_steps,
)
from custom_components.taskmate.storage import TaskMateStorage
from custom_components.taskmate.watch import chore_needs_input

UTC = timezone.utc
NOW = dt.datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC)
TODAY = NOW.date().isoformat()
YESTERDAY = (NOW.date() - dt.timedelta(days=1)).isoformat()
INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"

STEPS = [
    ChoreStep(name="Clothes away", id="s1"),
    ChoreStep(name="Toys in the box", id="s2"),
    ChoreStep(name="Make the bed", id="s3"),
]
KIDS = [Child(name="Mia", id="k1"), Child(name="Leo", id="k2")]


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _storage(chores, children) -> TaskMateStorage:
    from tests.conftest import FakeStore

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {
        "chores": [c.to_dict() for c in chores],
        "children": [c.to_dict() for c in children],
        "completions": [],
    }
    return storage


def _chore(**kwargs) -> Chore:
    kwargs.setdefault("requires_approval", False)
    kwargs.setdefault("points", 10)
    kwargs.setdefault("steps", [ChoreStep(name=s.name, id=s.id) for s in STEPS])
    return Chore(name="Tidy bedroom", id="tidy", **kwargs)


def _coord(chore: Chore, children=KIDS):
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    coord.hass.data = {}
    coord.storage = _storage([chore], children)
    coord._is_chore_completable_by_child = MagicMock(return_value=True)
    coord.is_chore_available_for_child = MagicMock(return_value=True)
    coord.weekly_target_met = MagicMock(return_value=False)
    coord._is_rotation_done_today = MagicMock(return_value=False)
    coord._apply_roulette_multiplier = MagicMock(side_effect=lambda c, cid, b: b)
    coord.difficulty_multiplier = MagicMock(return_value=1.0)
    coord._award_points = AsyncMock(side_effect=lambda child, pts, **kw: pts)
    coord._async_notify_pending_approval = AsyncMock()
    coord.async_refresh = AsyncMock()
    coord.badges = None
    return coord


def _patched(fn):
    with (
        patch("custom_components.taskmate.coord_chores.dt_util.now", return_value=NOW),
        patch("custom_components.taskmate.coord_steps.dt_util.now", return_value=NOW),
    ):
        return fn()


def _tick(coord, child_id, step_id, done=True):
    return _patched(lambda: run(coord.async_set_chore_step("tidy", child_id, step_id, done)))


def _complete(coord, child_id, **kwargs):
    return _patched(lambda: run(coord.async_complete_chore("tidy", child_id, **kwargs)))


def _done(coord, child_id):
    return _patched(lambda: coord.chore_steps_done(coord.get_chore("tidy"), child_id))


def _completions(coord, child_id="k1"):
    return [c for c in coord.storage.get_completions() if c.chore_id == "tidy" and c.child_id == child_id]


# ── the model ────────────────────────────────────────────────────────────────


def test_a_chore_has_no_steps_by_default():
    assert Chore(name="Dishes").steps == []
    assert "steps" in Chore(name="Dishes").to_dict()


def test_steps_round_trip_in_order():
    chore = _chore()
    back = Chore.from_dict(json.loads(json.dumps(chore.to_dict())))
    assert [(s.id, s.name) for s in back.steps] == [
        ("s1", "Clothes away"),
        ("s2", "Toys in the box"),
        ("s3", "Make the bed"),
    ]


def test_an_old_record_without_steps_loads():
    data = Chore(name="Dishes").to_dict()
    data.pop("steps")
    assert Chore.from_dict(data).steps == []


def test_loading_drops_broken_steps_instead_of_raising():
    steps = clean_chore_steps(
        [{"name": "A", "id": "a"}, {"name": "  "}, "junk", {"name": "B", "id": "a"}, {"name": "C"}]
    )
    assert [s.name for s in steps] == ["A", "C"]
    assert steps[1].id  # a step sent without an id gets one


def test_validate_refuses_bad_steps():
    with pytest.raises(TaskMateError):
        validate_chore_steps([{"name": ""}])
    with pytest.raises(TaskMateError):
        validate_chore_steps([{"name": f"s{i}"} for i in range(MAX_CHORE_STEPS + 1)])
    with pytest.raises(TaskMateError):
        validate_chore_steps([{"name": "A"}], task_type="timed")
    with pytest.raises(TaskMateError):
        validate_chore_steps([{"name": "A"}], has_times=True)
    assert validate_chore_steps(None) == []
    assert [s.name for s in validate_chore_steps([{"name": " A "}])] == ["A"]


def test_update_chore_refuses_steps_on_a_set_times_chore():
    chore = _chore()
    coord = _coord(chore)
    chore.times = [ChoreTime(name="Morning", start="07:00", end="08:00", points=1)]
    with pytest.raises(TaskMateError):
        run(coord.async_update_chore(chore))


# ── ticking and completing ───────────────────────────────────────────────────


def test_ticking_steps_earns_nothing():
    coord = _coord(_chore())
    assert _tick(coord, "k1", "s2") == ["s2"]
    assert _tick(coord, "k1", "s1") == ["s1", "s2"]  # always in step order
    assert _completions(coord) == []
    coord._award_points.assert_not_called()


def test_a_child_cannot_complete_before_every_step_is_ticked():
    coord = _coord(_chore())
    _tick(coord, "k1", "s1")
    _tick(coord, "k1", "s2")
    with pytest.raises(TaskMateError) as err:
        _complete(coord, "k1")
    assert err.value.translation_key == "chore_steps_incomplete"
    assert _completions(coord) == []


def test_the_last_step_lets_the_chore_complete_and_pay():
    coord = _coord(_chore())
    for step in ("s1", "s2", "s3"):
        _tick(coord, "k1", step)
    completion = _complete(coord, "k1")
    assert completion is not None and completion.approved
    assert completion.points_awarded == 10
    coord._award_points.assert_awaited_once()


def test_approval_rules_still_apply():
    coord = _coord(_chore(requires_approval=True))
    for step in ("s1", "s2", "s3"):
        _tick(coord, "k1", step)
    completion = _complete(coord, "k1")
    assert completion is not None and not completion.approved
    coord._award_points.assert_not_called()


def test_unticking_before_completion_is_allowed():
    coord = _coord(_chore())
    for step in ("s1", "s2", "s3"):
        _tick(coord, "k1", step)
    assert _tick(coord, "k1", "s2", done=False) == ["s1", "s3"]
    with pytest.raises(TaskMateError):
        _complete(coord, "k1")


def test_steps_are_per_child():
    coord = _coord(_chore())
    for step in ("s1", "s2", "s3"):
        _tick(coord, "k1", step)
    assert _done(coord, "k2") == []
    with pytest.raises(TaskMateError):
        _complete(coord, "k2")


def test_a_parent_can_complete_on_behalf_without_the_steps():
    coord = _coord(_chore())
    completion = _complete(coord, "k1", as_parent=True)
    assert completion is not None and completion.approved


def test_an_ordinary_chore_is_unaffected():
    coord = _coord(_chore(steps=[]))
    assert _complete(coord, "k1") is not None


def test_a_second_go_starts_with_a_clean_checklist():
    coord = _coord(_chore(daily_limit=2))
    for step in ("s1", "s2", "s3"):
        _tick(coord, "k1", step)
    assert _complete(coord, "k1") is not None
    assert _done(coord, "k1") == []
    with pytest.raises(TaskMateError):
        _complete(coord, "k1")
    for step in ("s1", "s2", "s3"):
        _tick(coord, "k1", step)
    assert _complete(coord, "k1") is not None
    assert len(_completions(coord)) == 2


def test_undoing_the_completion_brings_the_ticks_back():
    coord = _coord(_chore())
    for step in ("s1", "s2", "s3"):
        _tick(coord, "k1", step)
    completion = _complete(coord, "k1")
    assert _done(coord, "k1") == []
    coord.storage._data["completions"] = [c for c in coord.storage._data["completions"] if c["id"] != completion.id]
    assert _done(coord, "k1") == ["s1", "s2", "s3"]


def test_ticks_reset_when_the_day_rolls_over():
    coord = _coord(_chore())
    coord.storage.set_step_progress("tidy", "k1", YESTERDAY, 0, ["s1", "s2", "s3"])
    assert _done(coord, "k1") == []
    coord.storage.prune_step_progress(TODAY)
    assert "tidy" not in coord.storage._data.get("chore_steps", {})


def test_a_removed_step_no_longer_counts():
    coord = _coord(_chore())
    for step in ("s1", "s2", "s3"):
        _tick(coord, "k1", step)
    chore = coord.get_chore("tidy")
    chore.steps = chore.steps[:2] + [ChoreStep(name="New step", id="s4")]
    coord.storage._data["chores"] = [chore.to_dict()]
    assert _done(coord, "k1") == ["s1", "s2"]
    with pytest.raises(TaskMateError):
        _complete(coord, "k1")


def test_unknown_ids_raise():
    coord = _coord(_chore())
    with pytest.raises(TaskMateError):
        _tick(coord, "k1", "nope")
    with pytest.raises(TaskMateError):
        _tick(coord, "nobody", "s1")
    plain = _coord(_chore(steps=[]))
    with pytest.raises(TaskMateError):
        _tick(plain, "k1", "s1")


def test_deleting_a_child_or_chore_drops_their_ticks():
    coord = _coord(_chore())
    coord.storage.set_step_progress("tidy", "k1", TODAY, 0, ["s1"])
    coord.storage.set_step_progress("tidy", "k2", TODAY, 0, ["s2"])
    coord.storage.remove_step_progress_for_child("k1")
    assert list(coord.storage._data["chore_steps"]["tidy"]) == ["k2"]
    coord.storage.remove_step_progress_for_chore("tidy")
    assert "tidy" not in coord.storage._data["chore_steps"]


def test_a_watch_skips_a_multipart_chore():
    coord = MagicMock()
    coord.teamwork_size.return_value = 0
    assert chore_needs_input(coord, _chore())
    assert not chore_needs_input(coord, _chore(steps=[]))


# ── the data the card reads ──────────────────────────────────────────────────


def _record(chore, done=None):
    coordinator = object.__new__(TaskMateCoordinator)
    coordinator.effective_chore_points = MagicMock(side_effect=lambda ch: ch.points)
    coordinator.team_joined_ids = MagicMock(return_value=[])
    coordinator.chore_steps_done = MagicMock(side_effect=lambda ch, kid: (done or {}).get(kid, []))
    common = {"chores": [chore], "child_lookup": {k.id: k for k in KIDS}}
    return sensor_module._build_chores_list(coordinator, common)[0]


def test_chores_slice_carries_steps_and_ticks():
    record = _record(_chore(), done={"k1": ["s1"]})
    assert record["steps"] == [{"id": s.id, "name": s.name} for s in STEPS]
    assert record["step_done"] == {"k1": ["s1"]}


def test_chores_slice_omits_steps_on_an_ordinary_chore():
    record = _record(_chore(steps=[]))
    assert "steps" not in record and "step_done" not in record


def test_chores_slice_omits_step_done_while_nothing_is_ticked():
    record = _record(_chore())
    assert "steps" in record and "step_done" not in record


# ── the service ──────────────────────────────────────────────────────────────


def test_set_chore_step_service_is_declared_and_documented():
    services = yaml.safe_load((INTEGRATION / "services.yaml").read_text(encoding="utf-8"))
    fields = services["set_chore_step"]["fields"]
    assert all(fields[f]["required"] for f in ("chore_id", "child_id", "step_id"))
    strings = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
    assert set(strings["services"]["set_chore_step"]["fields"]) == {"chore_id", "child_id", "step_id", "done"}


def test_set_chore_step_is_registered_unregistered_and_gated_like_completing():
    source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    assert source.count("SERVICE_SET_CHORE_STEP,") >= 3  # import, register, unregister
    handler = re.search(r"async def handle_set_chore_step\(.*?\n\n", source, re.S).group(0)
    # A child ticks their own steps; a linked child can't tick a sibling's.
    assert "await _async_require_linked_child(hass, call, coordinator, child_id)" in handler


@pytest.mark.asyncio
async def test_linked_child_gate_refuses_another_user():
    import custom_components.taskmate as tm

    hass = MagicMock()
    hass.auth.async_get_user = AsyncMock(return_value=MagicMock(is_admin=False))
    call = MagicMock()
    call.context.user_id = "uid-leo"
    coord = MagicMock()
    coord.get_child.return_value = MagicMock(linked_user_id="uid-mia")
    coord.storage.get_children.return_value = []
    coord.storage.get_require_linked_child.return_value = False
    coord.storage.get_parent_user_ids.return_value = []
    with pytest.raises(tm.Unauthorized):
        await tm._async_require_linked_child(hass, call, coord, "k1")
