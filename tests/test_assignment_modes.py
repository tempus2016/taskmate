"""Tests for dynamic chore assignment (alternating/random) and calendar publishing.

Covers:
- `_compute_active_children` for each mode (everyone/alternating/random).
- `is_chore_available_for_child` respects the dynamic active child.
- `_publish_chore_to_calendars` fans out calendar.create_event per entity.
- Immediate publish on chore create/update.
- Scale smoke test: 50 chores x 5 children x 3 calendars run concurrently.
- Storage round-trip keeps legacy chores backwards-compatible.
"""

from __future__ import annotations

import datetime as dt
import time
from datetime import date, timezone
from unittest.mock import AsyncMock, MagicMock

from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore

from .conftest import dt_util_mock, run_async

UTC = timezone.utc


def _coord(children: list[Child], projection_days: int = 1) -> TaskMateCoordinator:
    """Build a coordinator with stub storage.

    The default `projection_days=1` keeps assertion counts sane for tests that
    only care about today's behaviour; pass a larger value when a test needs
    to exercise the multi-day projection directly.
    """
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.services = MagicMock()
    coord.hass.services.async_call = AsyncMock()
    coord.data = {}
    coord._unsub_midnight = None
    coord._unsub_prune = None

    by_id = {c.id: c for c in children}
    stored_chores: list[Chore] = []
    stored_task_groups: list = []
    settings = {"calendar_projection_days": str(projection_days)}

    storage = MagicMock()
    storage.get_children = MagicMock(return_value=list(children))
    storage.get_child = MagicMock(side_effect=lambda cid: by_id.get(cid))
    storage.get_chores = MagicMock(side_effect=lambda: list(stored_chores))
    storage.get_setting = MagicMock(side_effect=lambda key, default="": settings.get(key, default))
    storage.set_setting = MagicMock(side_effect=lambda key, value: settings.__setitem__(key, value))

    def _get_chore(cid):
        found = next((c for c in stored_chores if c.id == cid), None)
        # Return a snapshot so callers comparing against the stored state see
        # the pre-update values (mirrors real serialize/deserialize behaviour).
        return Chore.from_dict(found.to_dict()) if found is not None else None

    storage.get_chore = MagicMock(side_effect=_get_chore)
    storage.add_chore = MagicMock(side_effect=stored_chores.append)
    storage.update_chore = MagicMock(
        side_effect=lambda chore: stored_chores.__setitem__(
            next(i for i, c in enumerate(stored_chores) if c.id == chore.id), chore
        )
    )
    storage.async_save = AsyncMock()

    # Task group stubs — tests that don't touch groups still work because
    # get_task_groups returns an empty list.
    storage.get_task_groups = MagicMock(side_effect=lambda: list(stored_task_groups))

    def _get_task_group(gid):
        return next((g for g in stored_task_groups if g.id == gid), None)

    def _get_task_group_for_chore(chore_id):
        return next((g for g in stored_task_groups if chore_id in (g.chore_ids or [])), None)

    storage.get_task_group = MagicMock(side_effect=_get_task_group)
    storage.get_task_group_for_chore = MagicMock(side_effect=_get_task_group_for_chore)
    storage.add_task_group = MagicMock(side_effect=stored_task_groups.append)

    def _update_task_group(group):
        for i, g in enumerate(stored_task_groups):
            if g.id == group.id:
                stored_task_groups[i] = group
                return
        stored_task_groups.append(group)

    storage.update_task_group = MagicMock(side_effect=_update_task_group)
    storage.remove_task_group = MagicMock(
        side_effect=lambda gid: stored_task_groups.__setitem__(
            slice(None),
            [g for g in stored_task_groups if g.id != gid],
        )
    )
    storage.remove_chore_from_task_groups = MagicMock(
        side_effect=lambda cid: [
            setattr(g, "chore_ids", [c for c in g.chore_ids if c != cid])
            for g in stored_task_groups
            if cid in (g.chore_ids or [])
        ]
    )

    coord.storage = storage
    coord.async_refresh = AsyncMock()
    return coord


def test_compute_active_everyone_returns_assigned_list():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    chore = Chore(name="X", assigned_to=[a.id, b.id])
    assert coord._compute_active_children(chore, date(2026, 4, 20)) == [a.id, b.id]


def test_compute_active_alternating_rotates_day_by_day():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    anchor = date(2026, 4, 20)  # Monday
    chore = Chore(
        name="Litter box",
        assigned_to=[a.id, b.id],
        assignment_mode="alternating",
        assignment_rotation_anchor=anchor.isoformat(),
    )
    assert coord._compute_active_children(chore, anchor) == [a.id]
    assert coord._compute_active_children(chore, anchor + dt.timedelta(days=1)) == [b.id]
    assert coord._compute_active_children(chore, anchor + dt.timedelta(days=2)) == [a.id]
    # Three-child rotation wraps correctly
    c = Child(name="C")
    coord2 = _coord([a, b, c])
    chore2 = Chore(
        name="Table",
        assigned_to=[a.id, b.id, c.id],
        assignment_mode="alternating",
        assignment_rotation_anchor=anchor.isoformat(),
    )
    picks = [coord2._compute_active_children(chore2, anchor + dt.timedelta(days=i))[0] for i in range(4)]
    assert picks == [a.id, b.id, c.id, a.id]


def test_compute_active_alternating_defaults_to_all_children_when_unassigned():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    chore = Chore(name="Any", assignment_mode="alternating")
    today = date(2026, 4, 20)
    # Should pick one of the two children deterministically
    pick = coord._compute_active_children(chore, today)
    assert pick and pick[0] in (a.id, b.id)


def test_compute_active_random_is_stable_per_day():
    kids = [Child(name=f"K{i}") for i in range(5)]
    coord = _coord(kids)
    chore = Chore(name="Lottery", assigned_to=[c.id for c in kids], assignment_mode="random")
    today = date(2026, 4, 20)
    a1 = coord._compute_active_children(chore, today)
    a2 = coord._compute_active_children(chore, today)
    assert a1 == a2
    assert len(a1) == 1 and a1[0] in {c.id for c in kids}


def test_compute_active_random_varies_by_date():
    # Over a week's worth of dates at least two picks must differ for a 5-child pool.
    kids = [Child(name=f"K{i}") for i in range(5)]
    coord = _coord(kids)
    chore = Chore(name="Roulette", assigned_to=[c.id for c in kids], assignment_mode="random")
    picks = {coord._compute_active_children(chore, date(2026, 4, 20) + dt.timedelta(days=i))[0] for i in range(14)}
    assert len(picks) >= 2


def test_is_chore_available_respects_dynamic_assignment():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    # needs storage.get_last_completed for is_chore_available_for_child
    coord.storage.get_last_completed = MagicMock(return_value={})
    coord.storage.get_completions = MagicMock(return_value=[])
    anchor = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(anchor, dt.time(12, 0), tzinfo=UTC)
    chore = Chore(
        name="Dishes",
        assigned_to=[a.id, b.id],
        assignment_mode="alternating",
        assignment_rotation_anchor=anchor.isoformat(),
    )
    assert coord.is_chore_available_for_child(chore, a.id) is True
    assert coord.is_chore_available_for_child(chore, b.id) is False
    # Everyone mode is unchanged
    chore.assignment_mode = "everyone"
    assert coord.is_chore_available_for_child(chore, a.id) is True
    assert coord.is_chore_available_for_child(chore, b.id) is True


def test_rotation_chore_clears_for_pool_when_off_rotation_child_completes():
    """Regression for issue where a parent crediting User B (off rotation)
    leaves the chore visible on User A (today's active child)."""
    from custom_components.taskmate.models import ChoreCompletion

    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    coord.storage.get_last_completed = MagicMock(return_value={})
    anchor = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(anchor, dt.time(12, 0), tzinfo=UTC)
    chore = Chore(
        name="Bins",
        assigned_to=[a.id, b.id],
        assignment_mode="alternating",
        assignment_rotation_anchor=anchor.isoformat(),
    )
    # A is the active child today, B is off-rotation.
    assert coord._compute_active_children(chore, anchor) == [a.id]

    # Parent credits B (off-rotation) — completion lands on B today.
    completion = ChoreCompletion(
        chore_id=chore.id,
        child_id=b.id,
        completed_at=dt_util_mock.now(),
        approved=True,
    )
    coord.storage.get_completions = MagicMock(return_value=[completion])

    # Chore is now done for the whole rotation pool — invisible to A as well.
    assert coord._is_rotation_done_today(chore) is True
    assert coord.is_chore_available_for_child(chore, a.id) is False
    assert coord.is_chore_available_for_child(chore, b.id) is False

    # Sanity: with daily_limit=2 and only one completion so far, A still sees it.
    chore.daily_limit = 2
    assert coord._is_rotation_done_today(chore) is False
    assert coord.is_chore_available_for_child(chore, a.id) is True


def test_rotation_chore_with_pending_bonus_subtasks_stays_visible():
    """Regression for issue #365: when a rotation chore has bonus sub-tasks,
    completing the parent fills the daily quota (e.g. 1/1) — but the bonus
    sub-tasks render inside the parent card and must remain reachable until
    the active child has completed them. The chore should stay visible while
    bonus sub-tasks are pending."""
    from custom_components.taskmate.models import BonusSubTask, ChoreCompletion

    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    coord.storage.get_last_completed = MagicMock(return_value={})
    anchor = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(anchor, dt.time(12, 0), tzinfo=UTC)
    bonus = BonusSubTask(name="Extra wipe-down", points=2)
    chore = Chore(
        name="Bins",
        assigned_to=[a.id, b.id],
        assignment_mode="alternating",
        assignment_rotation_anchor=anchor.isoformat(),
        daily_limit=1,
        bonus_subtasks=[bonus],
    )
    # A is the active child today.
    assert coord._compute_active_children(chore, anchor) == [a.id]
    chore.assignment_current_child_id = a.id

    # A completes the parent — daily_limit is filled (1/1) but the bonus
    # sub-task is still pending, so the chore must stay visible.
    parent_completion = ChoreCompletion(
        chore_id=chore.id,
        child_id=a.id,
        completed_at=dt_util_mock.now(),
        approved=True,
    )
    coord.storage.get_completions = MagicMock(return_value=[parent_completion])
    assert coord._is_rotation_done_today(chore) is False
    assert coord.is_chore_available_for_child(chore, a.id) is True

    # Once A completes the bonus sub-task, the chore is fully done and hides.
    bonus_completion = ChoreCompletion(
        chore_id=chore.id,
        child_id=a.id,
        completed_at=dt_util_mock.now(),
        approved=True,
        bonus_subtask_id=bonus.id,
    )
    coord.storage.get_completions = MagicMock(return_value=[parent_completion, bonus_completion])
    assert coord._is_rotation_done_today(chore) is True
    assert coord.is_chore_available_for_child(chore, a.id) is False

    # Sanity: a rotation chore *without* bonus sub-tasks still hides as soon
    # as its quota is met (existing behaviour preserved).
    chore_no_bonus = Chore(
        name="Bins (no bonus)",
        assigned_to=[a.id, b.id],
        assignment_mode="alternating",
        assignment_rotation_anchor=anchor.isoformat(),
        daily_limit=1,
    )
    chore_no_bonus.assignment_current_child_id = a.id
    plain_completion = ChoreCompletion(
        chore_id=chore_no_bonus.id,
        child_id=a.id,
        completed_at=dt_util_mock.now(),
        approved=True,
    )
    coord.storage.get_completions = MagicMock(return_value=[plain_completion])
    assert coord._is_rotation_done_today(chore_no_bonus) is True


def test_everyone_mode_unaffected_by_rotation_done_helper():
    """Everyone-mode chores share no single daily quota across the pool, so
    the helper must not retire them after one child completes."""
    from custom_components.taskmate.models import ChoreCompletion

    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    coord.storage.get_last_completed = MagicMock(return_value={})
    today = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(today, dt.time(12, 0), tzinfo=UTC)
    chore = Chore(name="Brush teeth", assigned_to=[a.id, b.id])  # default everyone
    completion = ChoreCompletion(
        chore_id=chore.id,
        child_id=a.id,
        completed_at=dt_util_mock.now(),
        approved=True,
    )
    coord.storage.get_completions = MagicMock(return_value=[completion])
    assert coord._is_rotation_done_today(chore) is False
    assert coord.is_chore_available_for_child(chore, b.id) is True


def test_publish_fans_out_one_call_per_calendar():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    today = date(2026, 4, 20)
    chore = Chore(
        name="Litter box",
        assigned_to=[a.id, b.id],
        assignment_mode="alternating",
        assignment_rotation_anchor=today.isoformat(),
        publish_calendar_entities=["calendar.kids", "calendar.family", "calendar.shared"],
    )
    run_async(coord._publish_chore_to_calendars(chore, today))
    assert coord.hass.services.async_call.await_count == 3
    # Dedup: second call on the same day is a no-op.
    run_async(coord._publish_chore_to_calendars(chore, today))
    assert coord.hass.services.async_call.await_count == 3
    # Next day re-enables publishing.
    run_async(coord._publish_chore_to_calendars(chore, today + dt.timedelta(days=1)))
    assert coord.hass.services.async_call.await_count == 6
    # Summary references today's active child (A on day-0)
    first_call = coord.hass.services.async_call.await_args_list[0]
    payload = first_call.args[2]
    assert payload["summary"] == "Litter box — A"
    assert payload["start_date"] == today.isoformat()


def test_publish_is_noop_when_no_entities_configured():
    a = Child(name="A")
    coord = _coord([a])
    chore = Chore(name="Solo", assigned_to=[a.id])
    run_async(coord._publish_chore_to_calendars(chore, date(2026, 4, 20)))
    assert coord.hass.services.async_call.await_count == 0


def test_async_add_chore_publishes_immediately():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    dt_util_mock._now = dt.datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
    chore = run_async(
        coord.async_add_chore(
            name="Trash day",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor="2026-04-20",
            publish_calendar_entities=["calendar.kids", "calendar.family"],
        )
    )
    assert coord.hass.services.async_call.await_count == 2
    assert chore.publish_calendar_published_dates == ["2026-04-20"]
    assert chore.assignment_current_child_id == a.id


def test_async_update_chore_republishes_on_name_change():
    a = Child(name="A")
    coord = _coord([a])
    dt_util_mock._now = dt.datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
    chore = run_async(
        coord.async_add_chore(
            name="Old",
            assigned_to=[a.id],
            publish_calendar_entities=["calendar.x"],
        )
    )
    # One create_event from the initial add
    services = [c.args[1] for c in coord.hass.services.async_call.await_args_list]
    assert services == ["create_event"]
    # Simulate an edit flow: fetch a fresh copy, mutate, save.
    edited = coord.storage.get_chore(chore.id)
    edited.name = "New"
    run_async(coord.async_update_chore(edited))
    services = [c.args[1] for c in coord.hass.services.async_call.await_args_list]
    # Update pattern: get_events (cleanup probe) → (no delete because nothing matched) → create_event
    assert services == ["create_event", "get_events", "create_event"]


def test_scale_50_chores_5_children_3_calendars():
    kids = [Child(name=f"K{i}") for i in range(5)]
    coord = _coord(kids)
    today = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(today, dt.time(0, 0, 5), tzinfo=UTC)
    cals = ["calendar.a", "calendar.b", "calendar.c"]
    for i in range(50):
        chore = Chore(
            name=f"Chore {i}",
            assigned_to=[c.id for c in kids],
            assignment_mode="alternating" if i % 2 == 0 else "random",
            assignment_rotation_anchor=today.isoformat(),
            publish_calendar_entities=list(cals),
        )
        coord.storage.add_chore(chore)

    started = time.monotonic()
    run_async(coord._async_refresh_assignments_and_publish())
    duration = time.monotonic() - started

    assert coord.hass.services.async_call.await_count == 50 * 3
    # Concurrency guarantees the midnight tick stays sub-second even with 150 calls.
    assert duration < 5.0


def test_balanced_splits_evenly_across_pool():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    today = date(2026, 4, 20)
    pool = [a.id, b.id]
    chores = []
    for i in range(10):
        chore = Chore(name=f"C{i}", assigned_to=pool, assignment_mode="balanced")
        coord.storage.add_chore(chore)
        chores.append(chore)

    picks = [coord._compute_active_children(c, today)[0] for c in chores]
    counts = {cid: picks.count(cid) for cid in pool}
    # 10 chores, 2 children → exactly 5/5 with zero overlap.
    assert counts == {a.id: 5, b.id: 5}

    # 11th chore — ceiling split means 6/5.
    extra = Chore(name="C10", assigned_to=pool, assignment_mode="balanced")
    coord.storage.add_chore(extra)
    chores.append(extra)
    picks = [coord._compute_active_children(c, today)[0] for c in chores]
    counts = {cid: picks.count(cid) for cid in pool}
    assert sorted(counts.values()) == [5, 6]


def test_balanced_rotates_starting_child_across_days():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    chores = []
    for i in range(4):
        c = Chore(name=f"C{i}", assigned_to=[a.id, b.id], assignment_mode="balanced")
        coord.storage.add_chore(c)
        chores.append(c)

    def day_picks(d):
        return [coord._compute_active_children(c, d)[0] for c in chores]

    # Over a span of days the starting child should flip at least once.
    first_children = {day_picks(date(2026, 4, 20) + dt.timedelta(days=i))[0] for i in range(14)}
    assert len(first_children) == 2


def test_balanced_pools_are_independent():
    a, b = Child(name="A"), Child(name="B")
    c = Child(name="C")
    coord = _coord([a, b, c])
    today = date(2026, 4, 20)

    # Pool AB: 4 chores → 2/2 across {a, b}
    pool_ab = [a.id, b.id]
    ab_chores = []
    for i in range(4):
        ch = Chore(name=f"AB{i}", assigned_to=pool_ab, assignment_mode="balanced")
        coord.storage.add_chore(ch)
        ab_chores.append(ch)

    # Pool BC: 2 chores → 1/1 across {b, c}; must not be affected by pool AB.
    pool_bc = [b.id, c.id]
    bc_chores = []
    for i in range(2):
        ch = Chore(name=f"BC{i}", assigned_to=pool_bc, assignment_mode="balanced")
        coord.storage.add_chore(ch)
        bc_chores.append(ch)

    ab_picks = [coord._compute_active_children(ch, today)[0] for ch in ab_chores]
    bc_picks = [coord._compute_active_children(ch, today)[0] for ch in bc_chores]
    assert set(ab_picks) == {a.id, b.id}
    assert sorted(ab_picks).count(a.id) == 2
    assert set(bc_picks) == {b.id, c.id}


def test_timed_event_uses_time_category_window():
    a = Child(name="A")
    coord = _coord([a])
    today = date(2026, 4, 20)
    chore = Chore(
        name="Dishes",
        assigned_to=[a.id],
        time_category="evening",
        publish_calendar_entities=["calendar.x"],
    )
    run_async(coord._publish_chore_to_calendars(chore, today))
    args = coord.hass.services.async_call.await_args_list[0].args
    payload = args[2]
    assert payload["start_date_time"] == "2026-04-20T17:00:00"
    assert payload["end_date_time"] == "2026-04-20T21:00:00"
    assert "start_date" not in payload
    assert payload["description"] == f"taskmate:chore:{chore.id}"


def test_anytime_chore_still_emits_all_day_event():
    a = Child(name="A")
    coord = _coord([a])
    chore = Chore(
        name="Open",
        assigned_to=[a.id],
        time_category="anytime",
        publish_calendar_entities=["calendar.x"],
    )
    run_async(coord._publish_chore_to_calendars(chore, date(2026, 4, 20)))
    payload = coord.hass.services.async_call.await_args_list[0].args[2]
    assert payload["start_date"] == "2026-04-20"
    assert payload["end_date"] == "2026-04-21"
    assert "start_date_time" not in payload


def test_update_chore_cleans_up_old_events_before_republishing():
    a = Child(name="A")
    coord = _coord([a])
    dt_util_mock._now = dt.datetime(2026, 4, 20, 10, 0, tzinfo=UTC)

    chore = run_async(
        coord.async_add_chore(
            name="Old Name",
            assigned_to=[a.id],
            publish_calendar_entities=["calendar.x"],
        )
    )
    marker = coord._chore_event_marker(chore)
    # 1 publish from create.
    assert coord.hass.services.async_call.await_count == 1

    # Mock calendar.get_events to return one event that carries our marker.
    async def _service_side_effect(domain, service, data, *args, **kwargs):
        if service == "get_events":
            return {
                data["entity_id"]: {
                    "events": [
                        {"uid": "evt-abc", "summary": "Old Name — A", "description": marker},
                        {"uid": "evt-foreign", "summary": "Unrelated", "description": ""},
                    ]
                }
            }
        return None

    coord.hass.services.async_call.side_effect = _service_side_effect

    edited = coord.storage.get_chore(chore.id)
    edited.name = "New Name"
    run_async(coord.async_update_chore(edited))

    services_seen = [call.args[1] for call in coord.hass.services.async_call.await_args_list]
    assert "get_events" in services_seen
    assert "delete_event" in services_seen
    assert services_seen.count("delete_event") == 1  # foreign event left alone
    # and the new event got created after the purge
    assert services_seen[-1] == "create_event"
    new_payload = coord.hass.services.async_call.await_args_list[-1].args[2]
    assert new_payload["summary"] == "New Name — A"


def test_remove_chore_cleans_up_events():
    a = Child(name="A")
    coord = _coord([a])
    dt_util_mock._now = dt.datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
    chore = run_async(
        coord.async_add_chore(
            name="Trash",
            assigned_to=[a.id],
            publish_calendar_entities=["calendar.family"],
        )
    )
    marker = coord._chore_event_marker(chore)

    # Fake a stored event we previously published.
    async def _service_side_effect(domain, service, data, *args, **kwargs):
        if service == "get_events":
            return {
                data["entity_id"]: {
                    "events": [
                        {"uid": "evt-purge-me", "summary": "Trash — A", "description": marker},
                    ]
                }
            }
        return None

    coord.hass.services.async_call.side_effect = _service_side_effect
    # Storage needs these mocks for async_remove_chore's cleanup pass
    coord.storage.remove_chore = MagicMock()
    coord.storage.remove_completions_for_chore = MagicMock()
    coord.storage.remove_last_completed_for_chore = MagicMock()

    run_async(coord.async_remove_chore(chore.id))
    services_seen = [call.args[1] for call in coord.hass.services.async_call.await_args_list]
    assert services_seen.count("get_events") == 1
    assert services_seen.count("delete_event") == 1
    coord.storage.remove_chore.assert_called_once_with(chore.id)


def test_chore_from_dict_defaults_are_legacy_safe():
    legacy = {"name": "Legacy"}
    chore = Chore.from_dict(legacy)
    assert chore.assignment_mode == "everyone"
    assert chore.assignment_rotation_anchor == ""
    assert chore.assignment_current_child_id == ""
    assert chore.publish_calendar_entities == []
    assert chore.publish_calendar_published_dates == []
    # Round-trip preserves the new fields
    restored = Chore.from_dict(chore.to_dict())
    assert restored.assignment_mode == "everyone"
    assert restored.publish_calendar_entities == []
    assert restored.publish_calendar_published_dates == []
    # Back-compat: legacy records with the old scalar seed the new list
    migrated = Chore.from_dict({"name": "Old", "publish_calendar_last_date": "2026-04-20"})
    assert migrated.publish_calendar_published_dates == ["2026-04-20"]


# ---------------------------------------------------------------------------
# Availability-aware assignment
# ---------------------------------------------------------------------------


class _FakeState:
    """Minimal stand-in for homeassistant.core.State used by hass.states.get."""

    def __init__(self, state: str) -> None:
        self.state = state


class _FakeEvent:
    """Minimal stand-in for an HA Event — coordinator only reads .data."""

    def __init__(self, entity_id: str) -> None:
        self.data = {"entity_id": entity_id}


def _states_lookup(mapping: dict[str, str]):
    """Build a hass.states.get(entity_id) stub from an {entity_id: state} dict."""
    return MagicMock(side_effect=lambda eid: _FakeState(mapping[eid]) if eid in mapping else None)


class TestAvailabilityAwareAssignment:
    def test_require_availability_off_ignores_entity(self):
        # Even with an availability sensor saying "off", a chore without
        # require_availability rotates normally.
        a = Child(name="A", availability_entity="binary_sensor.a", id="kidA")
        b = Child(name="B", id="kidB")
        coord = _coord([a, b])
        coord.hass.states.get = _states_lookup({"binary_sensor.a": "off"})
        anchor = date(2026, 4, 20)
        chore = Chore(
            name="X",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
        )
        # Day 0 normally picks A — and does, because the skip is disabled.
        assert coord._compute_active_children(chore, anchor) == [a.id]

    def test_alternating_skips_unavailable_child(self):
        a = Child(name="A", availability_entity="binary_sensor.a", id="kidA")
        b = Child(name="B", id="kidB")
        coord = _coord([a, b])
        coord.hass.states.get = _states_lookup({"binary_sensor.a": "off"})
        anchor = date(2026, 4, 20)
        chore = Chore(
            name="X",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
            require_availability=True,
        )
        # Day 0 would be A; A is away so we skip to B.
        assert coord._compute_active_children(chore, anchor) == [b.id]
        # Day 1 naturally falls on B too; stays B.
        assert coord._compute_active_children(chore, anchor + dt.timedelta(days=1)) == [b.id]

    def test_random_skips_unavailable_child(self):
        # Deterministic seed: random picks are stable per (chore.id, date).
        # We pick a fake chore id whose hash lands on 'A' for this date, then
        # flip A's sensor off and assert it reroutes. The test is stable
        # because _skip_unavailable walks forward from the original idx.
        a = Child(name="A", availability_entity="binary_sensor.a", id="kidA")
        b = Child(name="B", id="kidB")
        coord = _coord([a, b])
        coord.hass.states.get = _states_lookup({"binary_sensor.a": "on"})
        today = date(2026, 4, 20)
        base = Chore(
            name="R",
            assigned_to=[a.id, b.id],
            assignment_mode="random",
            require_availability=True,
            id="reward_alpha",
        )
        original_pick = coord._compute_active_children(base, today)[0]
        coord.hass.states.get = _states_lookup(
            {
                "binary_sensor.a": "off" if original_pick == a.id else "on",
            }
        )
        # Only flip the originally picked child away — if it was A, A's sensor
        # is off; if it was B, A stays on and we'd expect no change.
        result = coord._compute_active_children(base, today)[0]
        if original_pick == a.id:
            assert result == b.id
        else:
            assert result == b.id  # unchanged; B was already picked

    def test_balanced_skips_unavailable_child(self):
        a = Child(name="A", availability_entity="binary_sensor.a", id="kidA")
        b = Child(name="B", id="kidB")
        coord = _coord([a, b])
        coord.hass.states.get = _states_lookup({"binary_sensor.a": "off"})
        today = date(2026, 4, 20)
        chores = [
            Chore(
                name=f"C{i}",
                assigned_to=[a.id, b.id],
                assignment_mode="balanced",
                require_availability=True,
                id=f"c{i}",
            )
            for i in range(4)
        ]
        for c in chores:
            coord.storage.add_chore(c)
        picks = [coord._compute_active_children(c, today)[0] for c in chores]
        # With A unavailable, every balanced chore must land on B.
        assert all(p == b.id for p in picks)

    def test_everyone_filters_unavailable_children(self):
        a = Child(name="A", availability_entity="binary_sensor.a", id="kidA")
        b = Child(name="B", id="kidB")
        coord = _coord([a, b])
        coord.hass.states.get = _states_lookup({"binary_sensor.a": "off"})
        chore = Chore(name="X", assigned_to=[a.id, b.id], require_availability=True)
        # Everyone mode with require_availability filters A out.
        assert coord._compute_active_children(chore, date(2026, 4, 20)) == [b.id]

    def test_all_unavailable_hides_chore(self):
        a = Child(name="A", availability_entity="binary_sensor.a", id="kidA")
        b = Child(name="B", availability_entity="binary_sensor.b", id="kidB")
        coord = _coord([a, b])
        coord.hass.states.get = _states_lookup({"binary_sensor.a": "off", "binary_sensor.b": "off"})
        anchor = date(2026, 4, 20)
        chore = Chore(
            name="X",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
            require_availability=True,
        )
        assert coord._compute_active_children(chore, anchor) == []

    def test_missing_entity_treated_as_available(self):
        a = Child(name="A", availability_entity="binary_sensor.not_registered", id="kidA")
        b = Child(name="B", id="kidB")
        coord = _coord([a, b])
        coord.hass.states.get = _states_lookup({})  # nothing registered
        anchor = date(2026, 4, 20)
        chore = Chore(
            name="X",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
            require_availability=True,
        )
        # Broken sensor → fail-open; A stays picked.
        assert coord._compute_active_children(chore, anchor) == [a.id]

    def test_unknown_state_treated_as_available(self):
        a = Child(name="A", availability_entity="binary_sensor.a", id="kidA")
        b = Child(name="B", id="kidB")
        coord = _coord([a, b])
        coord.hass.states.get = _states_lookup({"binary_sensor.a": "unknown"})
        anchor = date(2026, 4, 20)
        chore = Chore(
            name="X",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
            require_availability=True,
        )
        assert coord._compute_active_children(chore, anchor) == [a.id]

    def test_child_without_availability_entity_always_available(self):
        a = Child(name="A", id="kidA")  # no availability_entity
        b = Child(name="B", id="kidB")
        coord = _coord([a, b])
        coord.hass.states.get = MagicMock(return_value=None)
        anchor = date(2026, 4, 20)
        chore = Chore(
            name="X",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
            require_availability=True,
        )
        assert coord._compute_active_children(chore, anchor) == [a.id]

    def test_state_change_event_reassigns_chore(self):
        a = Child(name="A", availability_entity="binary_sensor.a", id="kidA")
        b = Child(name="B", id="kidB")
        coord = _coord([a, b])
        anchor = date(2026, 4, 20)
        # Seed: A is home, chore picks A.
        coord.hass.states.get = _states_lookup({"binary_sensor.a": "on"})
        chore = Chore(
            name="X",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
            require_availability=True,
            assignment_current_child_id=a.id,
            id="chore1",
        )
        coord.storage.add_chore(chore)
        coord.storage.get_completions = MagicMock(return_value=[])
        # A leaves → reevaluate should move the chore to B.
        coord.hass.states.get = _states_lookup({"binary_sensor.a": "off"})
        run_async(coord._async_reevaluate_availability())
        updated = coord.storage.get_chore("chore1")
        assert updated.assignment_current_child_id == b.id

    def test_state_change_event_skips_completed_chore(self):
        a = Child(name="A", availability_entity="binary_sensor.a", id="kidA")
        b = Child(name="B", id="kidB")
        coord = _coord([a, b])
        anchor = date(2026, 4, 20)
        coord.hass.states.get = _states_lookup({"binary_sensor.a": "off"})
        chore = Chore(
            name="X",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
            require_availability=True,
            assignment_current_child_id=a.id,
            id="chore1",
        )
        coord.storage.add_chore(chore)

        # Today in dt_util_mock is 2024-03-20 (see conftest).
        from custom_components.taskmate.models import ChoreCompletion

        today_dt = dt_util_mock.now()
        completion = ChoreCompletion(
            chore_id="chore1",
            child_id=a.id,
            completed_at=today_dt,
            approved=True,
        )
        coord.storage.get_completions = MagicMock(return_value=[completion])

        run_async(coord._async_reevaluate_availability())
        # Chore stays on A because it's already done today.
        updated = coord.storage.get_chore("chore1")
        assert updated.assignment_current_child_id == a.id

    def test_state_change_for_unrelated_entity_is_ignored(self):
        a = Child(name="A", availability_entity="binary_sensor.a", id="kidA")
        b = Child(name="B", id="kidB")
        coord = _coord([a, b])
        coord.hass.states.get = _states_lookup({"binary_sensor.a": "on"})
        # Filter: fire an event for an entity no child is linked to.
        event = _FakeEvent("binary_sensor.something_else")
        # Callback does not schedule a reeval (hass.async_create_task is the
        # FakeHass no-op anyway, but we still assert the tracked filter
        # short-circuits before scheduling).
        called = []
        original = coord.hass.async_create_task

        def _capture(coro):
            called.append(coro)
            return original(coro) if callable(original) else None

        coord.hass.async_create_task = _capture
        coord._availability_state_changed(event)
        assert called == []


# ---------------------------------------------------------------------------
# Skip / Manual-start / Task group coverage
# ---------------------------------------------------------------------------


class TestSkipChore:
    """Skip advances today's rotation pointer; tomorrow resumes original schedule."""

    def test_skip_advances_alternating_pointer_today_only(self):
        from custom_components.taskmate.models import TaskGroup  # noqa: F401 (ensure importable)

        a, b, c = Child(name="A"), Child(name="B"), Child(name="C")
        coord = _coord([a, b, c])
        anchor = date(2026, 4, 20)
        chore = Chore(
            name="Bins",
            assigned_to=[a.id, b.id, c.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
        )
        coord.storage.add_chore(chore)

        # Today = anchor day → A.
        dt_util_mock._now = dt.datetime.combine(anchor, dt.time(12, 0), tzinfo=UTC)
        assert coord._compute_active_children(chore, anchor) == [a.id]

        # Skip today → pointer advances to B.
        run_async(coord.async_skip_chore(chore.id))
        updated = coord.storage.get_chore(chore.id)
        assert updated.skip_date == anchor.isoformat()
        assert updated.skip_count == 1
        assert coord._compute_active_children(updated, anchor) == [b.id]

        # Skip again → C.
        run_async(coord.async_skip_chore(chore.id))
        updated = coord.storage.get_chore(chore.id)
        assert updated.skip_count == 2
        assert coord._compute_active_children(updated, anchor) == [c.id]

        # Tomorrow's compute MUST ignore stale skip state (still set today)
        # since skip_date != tomorrow.
        tomorrow = anchor + dt.timedelta(days=1)
        assert coord._compute_active_children(updated, tomorrow) == [b.id]

    def test_skip_rejects_everyone_mode(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        chore = Chore(name="Brush teeth", assigned_to=[a.id, b.id])  # mode = everyone
        coord.storage.add_chore(chore)
        try:
            run_async(coord.async_skip_chore(chore.id))
        except ValueError as err:
            assert "everyone" in str(err)
            return
        raise AssertionError("Expected ValueError for everyone-mode skip")

    def test_skip_rejects_pool_size_one(self):
        a = Child(name="A")
        coord = _coord([a])
        chore = Chore(
            name="Solo",
            assigned_to=[a.id],
            assignment_mode="alternating",
            assignment_rotation_anchor="2026-04-20",
        )
        coord.storage.add_chore(chore)
        try:
            run_async(coord.async_skip_chore(chore.id))
        except ValueError as err:
            assert "pool" in str(err).lower()
            return
        raise AssertionError("Expected ValueError for single-child pool skip")

    def test_skip_cycles_through_unassigned_and_back(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        chore = Chore(
            name="Bins",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor="2026-04-20",
        )
        coord.storage.add_chore(chore)
        dt_util_mock._now = dt.datetime(2026, 4, 20, 12, 0, tzinfo=UTC)

        # A is the initial assignee.
        assert coord._compute_active_children(chore, date(2026, 4, 20)) == [a.id]

        # Skip 1: A → B
        run_async(coord.async_skip_chore(chore.id))
        updated = coord.storage.get_chore(chore.id)
        assert updated.skip_count == 1
        assert updated.assignment_current_child_id == b.id

        # Skip 2: B → unassigned
        run_async(coord.async_skip_chore(chore.id))
        updated = coord.storage.get_chore(chore.id)
        assert updated.skip_count == 2
        assert updated.assignment_current_child_id == ""

        # Skip 3: unassigned → back to A
        run_async(coord.async_skip_chore(chore.id))
        updated = coord.storage.get_chore(chore.id)
        assert updated.skip_count == 0
        assert updated.assignment_current_child_id == a.id

    def test_skip_affects_random_mode(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        today = date(2026, 4, 20)
        chore = Chore(
            name="Roulette",
            assigned_to=[a.id, b.id],
            assignment_mode="random",
        )
        coord.storage.add_chore(chore)
        dt_util_mock._now = dt.datetime.combine(today, dt.time(12, 0), tzinfo=UTC)
        before = coord._compute_active_children(chore, today)
        run_async(coord.async_skip_chore(chore.id))
        updated = coord.storage.get_chore(chore.id)
        after = coord._compute_active_children(updated, today)
        # Pool size 2 → skip must shift to the other child.
        assert before != after

    def test_midnight_refresh_clears_stale_skip_state(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        chore = Chore(
            name="Bins",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor="2026-04-20",
            skip_date="2026-04-20",
            skip_count=1,
        )
        coord.storage.add_chore(chore)
        # Midnight rolls over to 2026-04-21 — skip state is stale.
        dt_util_mock._now = dt.datetime(2026, 4, 21, 0, 0, 5, tzinfo=UTC)
        run_async(coord._async_refresh_assignments_and_publish())
        updated = coord.storage.get_chore(chore.id)
        assert updated.skip_date == ""
        assert updated.skip_count == 0


class TestManualStart:
    """Manual-start reorders alternating pool and pins cache for random/balanced."""

    def test_manual_start_alternating_reorders_pool(self):
        a, b, c = Child(name="A"), Child(name="B"), Child(name="C")
        coord = _coord([a, b, c])
        anchor = date(2026, 4, 20)
        dt_util_mock._now = dt.datetime.combine(anchor, dt.time(12, 0), tzinfo=UTC)
        chore = run_async(
            coord.async_add_chore(
                name="Bins",
                assigned_to=[a.id, b.id, c.id],
                assignment_mode="alternating",
                assignment_rotation_anchor=anchor.isoformat(),
                manual_start_child_id=b.id,
            )
        )
        # Pool should now start with B (today's active child).
        assert chore.assigned_to[0] == b.id
        assert chore.assignment_current_child_id == b.id
        # Day 1 in the rotation uses the new anchor + new pool order.
        new_anchor = date.fromisoformat(chore.assignment_rotation_anchor)
        assert coord._compute_active_children(chore, new_anchor + dt.timedelta(days=1))[0] == chore.assigned_to[1]

    def test_manual_start_random_pins_today_only(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        today = date(2026, 4, 20)
        dt_util_mock._now = dt.datetime.combine(today, dt.time(12, 0), tzinfo=UTC)
        chore = run_async(
            coord.async_add_chore(
                name="Roulette",
                assigned_to=[a.id, b.id],
                assignment_mode="random",
                manual_start_child_id=a.id,
            )
        )
        assert chore.assignment_current_child_id == a.id


class TestTaskGroups:
    """Sticky & Spread policies, and group-aware daily assignment."""

    def test_sticky_forces_followers_onto_leader_pick(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        anchor = date(2026, 4, 20)
        leader = Chore(
            name="Vacuum",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
        )
        follower = Chore(
            name="Mop",
            assigned_to=[a.id, b.id],
            assignment_mode="random",
        )
        coord.storage.add_chore(leader)
        coord.storage.add_chore(follower)
        run_async(coord.async_add_task_group(name="Clean", policy="sticky", chore_ids=[leader.id, follower.id]))

        dt_util_mock._now = dt.datetime.combine(anchor, dt.time(12, 0), tzinfo=UTC)
        daily = coord._compute_daily_assignments(anchor)
        # Leader is A (alternating day-0). Follower must match.
        assert daily[leader.id] == a.id
        assert daily[follower.id] == a.id

    def test_sticky_fallback_when_leader_pick_not_in_follower_pool(self):
        a, b, c = Child(name="A"), Child(name="B"), Child(name="C")
        coord = _coord([a, b, c])
        anchor = date(2026, 4, 20)
        leader = Chore(
            name="Lead",
            assigned_to=[a.id, b.id, c.id],  # can pick A
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
        )
        follower = Chore(
            name="Follow",
            assigned_to=[b.id, c.id],  # NO A in pool
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
        )
        coord.storage.add_chore(leader)
        coord.storage.add_chore(follower)
        run_async(coord.async_add_task_group(name="Grp", policy="sticky", chore_ids=[leader.id, follower.id]))

        dt_util_mock._now = dt.datetime.combine(anchor, dt.time(12, 0), tzinfo=UTC)
        daily = coord._compute_daily_assignments(anchor)
        assert daily[leader.id] == a.id
        # Follower keeps its raw pick (not A, since A isn't in pool).
        assert daily[follower.id] in {b.id, c.id}

    def test_spread_gives_distinct_children(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        today = date(2026, 4, 20)
        c1 = Chore(
            name="AM",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=today.isoformat(),
        )
        c2 = Chore(
            name="PM",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=today.isoformat(),
        )
        coord.storage.add_chore(c1)
        coord.storage.add_chore(c2)
        run_async(coord.async_add_task_group(name="Cat litter", policy="spread", chore_ids=[c1.id, c2.id]))

        daily = coord._compute_daily_assignments(today)
        assert daily[c1.id] != daily[c2.id]

    def test_spread_wraps_when_group_larger_than_pool(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        today = date(2026, 4, 20)
        chores = []
        for i in range(4):
            ch = Chore(
                name=f"C{i}",
                assigned_to=[a.id, b.id],
                assignment_mode="alternating",
                assignment_rotation_anchor=today.isoformat(),
            )
            coord.storage.add_chore(ch)
            chores.append(ch)
        run_async(coord.async_add_task_group(name="Big", policy="spread", chore_ids=[c.id for c in chores]))

        daily = coord._compute_daily_assignments(today)
        picks = [daily[c.id] for c in chores]
        # Must alternate: both children used exactly twice.
        assert picks.count(a.id) == 2
        assert picks.count(b.id) == 2
        # Adjacent entries differ (spread walks raw-indexed avoidance).
        for i in range(len(picks) - 1):
            assert picks[i] != picks[i + 1]

    def test_everyone_mode_chore_cannot_join_group(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        chore = Chore(name="Brush", assigned_to=[a.id, b.id])  # everyone
        coord.storage.add_chore(chore)
        try:
            run_async(coord.async_add_task_group(name="Bad", policy="sticky", chore_ids=[chore.id]))
        except ValueError as err:
            assert "everyone" in str(err).lower()
            return
        raise AssertionError("Expected ValueError for everyone-mode chore in group")

    def test_chore_cannot_belong_to_two_groups(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        c1 = Chore(
            name="C1", assigned_to=[a.id, b.id], assignment_mode="alternating", assignment_rotation_anchor="2026-04-20"
        )
        c2 = Chore(
            name="C2", assigned_to=[a.id, b.id], assignment_mode="alternating", assignment_rotation_anchor="2026-04-20"
        )
        coord.storage.add_chore(c1)
        coord.storage.add_chore(c2)
        run_async(coord.async_add_task_group(name="G1", policy="sticky", chore_ids=[c1.id, c2.id]))
        try:
            run_async(coord.async_add_task_group(name="G2", policy="spread", chore_ids=[c1.id]))
        except ValueError as err:
            assert "group" in str(err).lower()
            return
        raise AssertionError("Expected ValueError for duplicate group membership")

    def test_skip_on_sticky_follower_rejected(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        leader = Chore(
            name="L", assigned_to=[a.id, b.id], assignment_mode="alternating", assignment_rotation_anchor="2026-04-20"
        )
        follower = Chore(
            name="F", assigned_to=[a.id, b.id], assignment_mode="alternating", assignment_rotation_anchor="2026-04-20"
        )
        coord.storage.add_chore(leader)
        coord.storage.add_chore(follower)
        run_async(coord.async_add_task_group(name="G", policy="sticky", chore_ids=[leader.id, follower.id]))

        dt_util_mock._now = dt.datetime(2026, 4, 20, 12, 0, tzinfo=UTC)
        try:
            run_async(coord.async_skip_chore(follower.id))
        except ValueError as err:
            assert "leader" in str(err).lower() or "follower" in str(err).lower()
            return
        raise AssertionError("Expected ValueError for skipping sticky follower")

    def test_skip_on_sticky_leader_propagates_to_followers(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        anchor = date(2026, 4, 20)
        leader = Chore(
            name="L",
            assigned_to=[a.id, b.id],
            assignment_mode="alternating",
            assignment_rotation_anchor=anchor.isoformat(),
        )
        follower = Chore(name="F", assigned_to=[a.id, b.id], assignment_mode="random")
        coord.storage.add_chore(leader)
        coord.storage.add_chore(follower)
        run_async(coord.async_add_task_group(name="G", policy="sticky", chore_ids=[leader.id, follower.id]))

        dt_util_mock._now = dt.datetime.combine(anchor, dt.time(12, 0), tzinfo=UTC)
        # Pre-skip: leader = A, follower = A (sticky).
        daily = coord._compute_daily_assignments(anchor)
        assert daily[leader.id] == a.id
        assert daily[follower.id] == a.id

        # Skip leader.
        run_async(coord.async_skip_chore(leader.id))
        updated_leader = coord.storage.get_chore(leader.id)
        updated_follower = coord.storage.get_chore(follower.id)
        assert updated_leader.assignment_current_child_id == b.id
        assert updated_follower.assignment_current_child_id == b.id


class TestRemoveChoreFromGroups:
    """Deleting a chore strips its id from any group it was in."""

    def test_remove_chore_strips_from_group(self):
        a, b = Child(name="A"), Child(name="B")
        coord = _coord([a, b])
        c1 = Chore(
            name="C1", assigned_to=[a.id, b.id], assignment_mode="alternating", assignment_rotation_anchor="2026-04-20"
        )
        c2 = Chore(
            name="C2", assigned_to=[a.id, b.id], assignment_mode="alternating", assignment_rotation_anchor="2026-04-20"
        )
        coord.storage.add_chore(c1)
        coord.storage.add_chore(c2)
        run_async(coord.async_add_task_group(name="G", policy="sticky", chore_ids=[c1.id, c2.id]))

        run_async(coord.async_remove_chore(c1.id))
        groups = coord.storage.get_task_groups()
        assert len(groups) == 1
        assert c1.id not in groups[0].chore_ids
        assert c2.id in groups[0].chore_ids


# ---------------------------------------------------------------------------
# first_come (first come, first served) mode — issue #401
# ---------------------------------------------------------------------------


def test_add_chore_accepts_first_come_mode():
    """async_add_chore must preserve first_come (not silently fall back to everyone)."""
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    coord.storage.get_last_completed = MagicMock(return_value={})
    coord.storage.get_completions = MagicMock(return_value=[])
    dt_util_mock._now = dt.datetime.combine(date(2026, 4, 20), dt.time(9, 0), tzinfo=UTC)

    chore = run_async(coord.async_add_chore(name="Feed cat", assigned_to=[a.id, b.id], assignment_mode="first_come"))
    assert chore.assignment_mode == "first_come"
    # first_come has no single active child cached.
    assert chore.assignment_current_child_id == ""


def test_first_come_visible_to_whole_pool_until_claimed():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    coord.storage.get_last_completed = MagicMock(return_value={})
    coord.storage.get_completions = MagicMock(return_value=[])
    today = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(today, dt.time(9, 0), tzinfo=UTC)

    chore = Chore(name="Feed cat", assigned_to=[a.id, b.id], assignment_mode="first_come")
    assert sorted(coord._compute_active_children(chore, today)) == sorted([a.id, b.id])
    assert coord.is_chore_available_for_child(chore, a.id) is True
    assert coord.is_chore_available_for_child(chore, b.id) is True


def test_first_come_empty_assigned_means_all_children():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    coord.storage.get_last_completed = MagicMock(return_value={})
    coord.storage.get_completions = MagicMock(return_value=[])
    today = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(today, dt.time(9, 0), tzinfo=UTC)

    chore = Chore(name="Feed cat", assigned_to=[], assignment_mode="first_come")
    assert sorted(coord._compute_active_children(chore, today)) == sorted([a.id, b.id])


def test_first_come_first_claim_hides_for_others_and_reopens_on_reject():
    from custom_components.taskmate.models import ChoreCompletion

    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    coord.storage.get_last_completed = MagicMock(return_value={})
    today = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(today, dt.time(9, 0), tzinfo=UTC)
    chore = Chore(name="Feed cat", assigned_to=[a.id, b.id], assignment_mode="first_come")

    # A claims (pending approval -- approved=False still fills the quota).
    claim = ChoreCompletion(chore_id=chore.id, child_id=a.id, completed_at=dt_util_mock.now(), approved=False)
    coord.storage.get_completions = MagicMock(return_value=[claim])
    assert coord._is_rotation_done_today(chore) is True
    assert coord.is_chore_available_for_child(chore, a.id) is False
    assert coord.is_chore_available_for_child(chore, b.id) is False

    # Parent rejects -> completion removed -> reopens for the whole pool.
    coord.storage.get_completions = MagicMock(return_value=[])
    assert coord._is_rotation_done_today(chore) is False
    assert coord.is_chore_available_for_child(chore, a.id) is True
    assert coord.is_chore_available_for_child(chore, b.id) is True


def test_first_come_clamps_quota_to_one_winner():
    from custom_components.taskmate.models import ChoreCompletion

    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    coord.storage.get_last_completed = MagicMock(return_value={})
    today = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(today, dt.time(9, 0), tzinfo=UTC)
    # Even if daily_limit is mis-set to 2, first_come allows only one winner.
    chore = Chore(name="Feed cat", assigned_to=[a.id, b.id], assignment_mode="first_come", daily_limit=2)
    claim = ChoreCompletion(chore_id=chore.id, child_id=a.id, completed_at=dt_util_mock.now(), approved=True)
    coord.storage.get_completions = MagicMock(return_value=[claim])
    assert coord._is_rotation_done_today(chore) is True


def test_first_come_excluded_from_daily_assignments_and_cache():
    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    coord.storage.get_last_completed = MagicMock(return_value={})
    coord.storage.get_completions = MagicMock(return_value=[])
    today = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(today, dt.time(9, 0), tzinfo=UTC)
    chore = Chore(name="Feed cat", assigned_to=[a.id, b.id], assignment_mode="first_come")
    coord.storage.add_chore(chore)
    # No single assignee is recorded for first_come.
    assert chore.id not in coord._compute_daily_assignments(today)


def test_first_come_loser_completion_is_rejected():
    from custom_components.taskmate.models import ChoreCompletion

    a, b = Child(name="A"), Child(name="B")
    coord = _coord([a, b])
    coord.storage.get_last_completed = MagicMock(return_value={})
    coord._award_points = AsyncMock(return_value=10)
    coord.async_refresh = AsyncMock()
    coord.badges = None
    today = date(2026, 4, 20)
    dt_util_mock._now = dt.datetime.combine(today, dt.time(9, 0), tzinfo=UTC)
    chore = Chore(name="Feed cat", assigned_to=[a.id, b.id], assignment_mode="first_come", requires_approval=False)
    coord.storage.add_chore(chore)

    # A already won (completion on record).
    winning = ChoreCompletion(chore_id=chore.id, child_id=a.id, completed_at=dt_util_mock.now(), approved=True)
    coord.storage.get_completions = MagicMock(return_value=[winning])

    # The race loser is a soft rejection: silent no-op (returns None), no points
    # awarded — not an ERROR-logged exception.
    result = run_async(coord.async_complete_chore(chore.id, b.id))
    assert result is None
    coord._award_points.assert_not_called()
