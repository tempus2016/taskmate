"""Reject reasons (#976): a parent can say why a chore or reward was rejected."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coord_notifications import (
    NOTIFICATION_TYPES_BY_ID,
    NotificationCoordinator,
)
from custom_components.taskmate.coord_rejections import REJECTION_CARD_MAX, REJECTION_KEEP_MAX
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import (
    REJECT_REASON_MAX,
    Child,
    Chore,
    ChoreCompletion,
    Reward,
    RewardClaim,
)

from .conftest import dt_util_mock

UTC = dt.timezone.utc
NOW = dt.datetime(2024, 3, 20, 12, 0, tzinfo=UTC)


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def _pin_now():
    dt_util_mock._now = NOW
    yield
    dt_util_mock._now = NOW


def _coord(completions=(), claims=()):
    """A coordinator over a mocked store whose rejection log is a real list."""
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.bus.async_fire = MagicMock()
    coord.storage = MagicMock()
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    log: list[dict] = []
    coord.storage.get_rejections = MagicMock(side_effect=lambda: list(log))
    coord.storage.set_rejections = MagicMock(side_effect=lambda rows: log.__setitem__(slice(None), rows))
    coord.storage.get_completions = MagicMock(return_value=list(completions))
    coord.storage.get_reward_claims = MagicMock(return_value=list(claims))
    coord.storage.get_bounty = MagicMock(return_value=None)
    coord.notifications = MagicMock()
    coord.notifications.fire = AsyncMock()
    coord.notifications.clear_approval = AsyncMock()
    coord.get_chore = MagicMock(return_value=Chore(name="Tidy room", id="ch1"))
    coord.get_child = MagicMock(return_value=Child(name="Mia", id="c1"))
    coord.get_reward = MagicMock(return_value=Reward(name="Ice cream", cost=50, id="r1"))
    coord._log = log
    return coord


def _completion(cid="comp1", at=NOW - dt.timedelta(minutes=5), **kw):
    return ChoreCompletion(chore_id="ch1", child_id="c1", completed_at=at, approved=False, id=cid, **kw)


def _claim(cid="cl1", at=NOW - dt.timedelta(minutes=5)):
    return RewardClaim(reward_id="r1", child_id="c1", claimed_at=at, id=cid)


def _fired(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


# ── chores ───────────────────────────────────────────────────────────────


def test_a_chore_rejection_keeps_the_reason_and_tells_the_child():
    coord = _coord([_completion()])
    run(coord.async_reject_chore("comp1", reason="  Not   finished "))

    assert _fired(coord, "taskmate_chore_rejected")[0]["reason"] == "Not finished"
    (row,) = coord._log
    assert (row["kind"], row["child_id"], row["item_id"], row["item_name"], row["reason"]) == (
        "chore",
        "c1",
        "ch1",
        "Tidy room",
        "Not finished",
    )
    type_id, ctx = coord.notifications.fire.await_args.args
    assert type_id == "item_rejected"
    assert ctx["reason"] == "Not finished" and ctx["item_name"] == "Tidy room"
    assert coord.notifications.fire.await_args.kwargs["only_recipients"] == {"child:c1"}


def test_a_rejection_without_a_reason_logs_nothing():
    coord = _coord([_completion()])
    run(coord.async_reject_chore("comp1"))
    assert coord._log == []
    assert _fired(coord, "taskmate_chore_rejected")[0]["reason"] == ""
    # The child still hears it was sent back (the type is opt-in).
    assert coord.notifications.fire.await_args.args[1]["reason_text"] == ""


def test_a_childs_own_undo_carries_no_reason_and_no_notice():
    coord = _coord([_completion()])
    run(coord.async_reject_chore("comp1", event="taskmate_chore_undone", reason="sneaky"))
    assert coord._log == []
    assert "reason" not in _fired(coord, "taskmate_chore_undone")[0]
    coord.notifications.fire.assert_not_awaited()


def test_the_reason_is_capped():
    coord = _coord([_completion()])
    run(coord.async_reject_chore("comp1", reason="x" * 500))
    assert len(coord._log[0]["reason"]) == REJECT_REASON_MAX


# ── rewards ──────────────────────────────────────────────────────────────


def test_a_reward_rejection_keeps_the_reason_and_tells_the_child():
    coord = _coord(claims=[_claim()])
    run(coord.async_reject_reward("cl1", reason="Not today"))
    payload = _fired(coord, "taskmate_reward_rejected")[0]
    assert payload["reason"] == "Not today"
    assert coord._log[0]["kind"] == "reward" and coord._log[0]["item_id"] == "r1"
    assert coord.notifications.fire.await_args.args[1]["item_name"] == "Ice cream"


def test_an_approved_claim_is_still_refused():
    claim = _claim()
    claim.approved = True
    coord = _coord(claims=[claim])
    with pytest.raises(ValueError):
        run(coord.async_reject_reward("cl1", reason="late"))
    assert coord._log == []


# ── what the card shows ──────────────────────────────────────────────────


def _row(kind="chore", item="ch1", at=NOW - dt.timedelta(hours=1), reason="Needs redoing", child="c1"):
    return {
        "id": f"{kind}-{item}-{at.isoformat()}",
        "kind": kind,
        "child_id": child,
        "item_id": item,
        "item_name": item,
        "reason": reason,
        "rejected_at": at.isoformat(),
    }


def test_the_card_gets_the_latest_reason_per_item():
    coord = _coord()
    coord._log[:] = [
        _row(reason="old", at=NOW - dt.timedelta(hours=3)),
        _row(reason="new", at=NOW - dt.timedelta(hours=1)),
        _row(kind="reward", item="r1", reason="Not today"),
        _row(child="c2", reason="someone else"),
    ]
    rows = coord.rejections_for_child("c1")
    assert [(r["kind"], r["id"], r["reason"]) for r in rows] == [
        ("reward", "r1", "Not today"),
        ("chore", "ch1", "new"),
    ]


def test_a_newer_attempt_retires_the_reason():
    coord = _coord(
        completions=[_completion(at=NOW - dt.timedelta(minutes=10))],
        claims=[_claim(at=NOW - dt.timedelta(minutes=10))],
    )
    coord._log[:] = [_row(), _row(kind="reward", item="r1")]
    assert coord.rejections_for_child("c1") == []


def test_reasons_leave_the_card_after_a_day():
    coord = _coord()
    coord._log[:] = [_row(at=NOW - dt.timedelta(hours=25))]
    assert coord.rejections_for_child("c1") == []


def test_the_card_list_is_capped():
    coord = _coord()
    coord._log[:] = [_row(item=f"ch{i}") for i in range(REJECTION_CARD_MAX + 4)]
    assert len(coord.rejections_for_child("c1")) == REJECTION_CARD_MAX


def test_the_log_is_pruned_by_age_and_size():
    coord = _coord()
    coord._log[:] = [_row(at=NOW - dt.timedelta(days=8))]
    coord._record_rejection("chore", "c1", "ch1", "Tidy room", "why")
    assert [r["reason"] for r in coord._log] == ["why"]
    for i in range(REJECTION_KEEP_MAX + 5):
        coord._record_rejection("chore", "c1", f"ch{i}", "x", "why")
    assert len(coord._log) == REJECTION_KEEP_MAX


def test_removing_a_child_drops_their_reasons(hass):
    from custom_components.taskmate.storage import TaskMateStorage

    storage = TaskMateStorage(hass, "rej")
    run(storage.async_load())
    storage.set_rejections([_row(), _row(child="c2")])
    storage.remove_child("c1")
    assert [r["child_id"] for r in storage.get_rejections()] == ["c2"]


def test_old_stores_without_a_log_read_as_empty(hass):
    from custom_components.taskmate.storage import TaskMateStorage

    storage = TaskMateStorage(hass, "rej-old")
    run(storage.async_load())
    assert storage.get_rejections() == []
    storage._data["rejections"] = "garbage"
    assert storage.get_rejections() == []


# ── sensor attributes ────────────────────────────────────────────────────


def test_the_child_summary_carries_reasons_only_when_there_are_some():
    from .test_sensor_attributes import _stress_coordinator

    coord = _stress_coordinator()
    coord.rejections_for_child = MagicMock(
        side_effect=lambda cid: (
            [{"kind": "chore", "id": "chore-01", "reason": "Not finished", "at": "x"}] if cid == "child-0" else []
        )
    )
    common = sensor_module._compute_common(coord)
    summary = {c["id"]: c for c in sensor_module._build_children_summary(coord, common)}
    assert summary["child-0"]["rejections"][0]["reason"] == "Not finished"
    assert "rejections" not in summary["child-1"]


def test_the_activity_feed_lists_reasoned_rejections_within_the_cap():
    from .test_sensor_attributes import MAX_ATTR_BYTES, _stress_coordinator

    coord = _stress_coordinator()
    common = sensor_module._compute_common(coord)
    rows = [
        {
            **_row(kind="reward" if i % 2 else "chore", item=f"i{i}", reason="R" * REJECT_REASON_MAX, child="child-0"),
            "item_name": "N" * 60,
            "rejected_at": "2099-01-01T00:00:00+00:00",
        }
        for i in range(REJECTION_KEEP_MAX)
    ]
    txns = sensor_module._build_recent_transactions(common, rejections=rows)
    rejected = [t for t in txns if t["type"].endswith("_rejected")]
    # Newest few only, so a burst of long reasons can't crowd out the cap.
    assert len(rejected) == sensor_module._FEED_REJECTIONS_MAX
    assert {t["type"] for t in rejected} == {"chore_rejected", "reward_rejected"}
    chore = next(t for t in txns if t["type"] == "chore_rejected")
    assert chore["chore_name"] and chore["reason"] and "reward_name" not in chore
    attrs = {
        "recent_completions": sensor_module._build_recent_completions(common),
        "recent_transactions": txns,
    }
    assert len(json.dumps(attrs, default=str).encode()) < MAX_ATTR_BYTES


def test_overview_stays_under_the_cap_with_every_child_holding_reasons():
    from .test_sensor_attributes import MAX_ATTR_BYTES, _stress_coordinator

    coord = _stress_coordinator()
    coord.rejections_for_child = MagicMock(
        return_value=[
            {"kind": "chore", "id": f"chore-{i:02d}", "reason": "R" * REJECT_REASON_MAX, "at": NOW.isoformat()}
            for i in range(REJECTION_CARD_MAX)
        ]
    )
    common = sensor_module._compute_common(coord)
    children = sensor_module._build_children_summary(coord, common)
    assert len(json.dumps({"children": children}, default=str).encode()) < MAX_ATTR_BYTES


# ── websocket + mobile action ────────────────────────────────────────────


def _ws_coordinator():
    coordinator = MagicMock(spec=TaskMateCoordinator)
    coordinator.async_reject_chore = AsyncMock()
    coordinator.async_reject_reward = AsyncMock()
    coordinator.async_record_audit = AsyncMock()
    return coordinator


def _hass_with(coordinator):
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry1": coordinator}}
    return hass


def _connection():
    connection = MagicMock()
    connection.user.is_admin = True
    return connection


@pytest.mark.asyncio
async def test_ws_reject_forwards_the_reason():
    coordinator = _ws_coordinator()
    await ws._ws_reject_chore(
        _hass_with(coordinator), _connection(), {"id": 1, "completion_id": "x1", "reason": "Not finished"}
    )
    coordinator.async_reject_chore.assert_awaited_once_with("x1", reason="Not finished")
    await ws._ws_reject_reward(_hass_with(coordinator), _connection(), {"id": 2, "claim_id": "c1"})
    coordinator.async_reject_reward.assert_awaited_once_with("c1", reason="")


def test_item_rejected_is_a_child_type_off_by_default():
    meta = NOTIFICATION_TYPES_BY_ID["item_rejected"]
    assert meta.audience == "child" and meta.default_enabled is False and meta.actionable is False


def test_the_notice_reads_well_with_and_without_a_reason(hass):
    notif = NotificationCoordinator(hass, MagicMock())
    meta = NOTIFICATION_TYPES_BY_ID["item_rejected"]
    with_reason = notif._render_template(
        meta, {"child_name": "Mia", "item_name": "Tidy room", "reason_text": ": Not finished"}
    )
    without = notif._render_template(meta, {"child_name": "Mia", "item_name": "Tidy room", "reason_text": ""})
    assert with_reason.endswith("'Tidy room' was sent back: Not finished")
    assert without.endswith("'Tidy room' was sent back")
