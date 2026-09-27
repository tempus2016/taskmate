"""Chore quality rating: 1-3 stars at approval scale the points (#927).

The rating is optional and off by default. When on, it scales the chore's base
points by the chosen star's multiplier, is stored on the completion, and —
because the scaled total is what lands in ``points_awarded`` — undo and reject
reverse exactly what the rating paid.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import pathlib
import re
from datetime import timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import ChoreCompletion, NotificationRoute, ParentRecipient, RewardClaim
from custom_components.taskmate.storage import TaskMateStorage

UTC = timezone.utc
ROOT = pathlib.Path(__file__).resolve().parent.parent
WWW = ROOT / "custom_components" / "taskmate" / "www"


def _now():
    # A Wednesday, so the weekend multiplier never rides on top.
    return dt.datetime(2024, 3, 20, 12, 0, 0, tzinfo=UTC)


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
    coord._dt_now = _now()
    coord.async_refresh = AsyncMock()
    coord._async_notify_pending_approval = AsyncMock()
    notifications = AsyncMock()
    notifications._has_outstanding_chores_today = lambda _cid: True
    coord.notifications = notifications
    return coord, storage


def _run(coro_factory):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_factory())
    finally:
        loop.close()
        asyncio.set_event_loop(None)


def _stored(coord, completion_id):
    return next(c for c in coord.storage.get_completions() if c.id == completion_id)


async def _pending(coord, points=20):
    child = await coord.async_add_child("Alice")
    chore = await coord.async_add_chore(
        "Tidy up",
        points=points,
        requires_approval=True,
        schedule_mode="specific_days",
        assigned_to=[child.id],
    )
    completion = await coord.async_complete_chore(chore.id, child.id)
    assert completion is not None and completion.approved is False
    return child, chore, completion


def _approve(settings, rating=None, points=None, base=20):
    """Approve one pending completion; return (child points, stored completion)."""

    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _ = await _make_system(settings)
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, _chore, completion = await _pending(coord, points=base)
            await coord.async_approve_chore(completion.id, rating=rating, points=points)
            return coord.get_child(child.id).points, _stored(coord, completion.id)

    return _run(scenario)


ON = {"quality_rating_enabled": True}


# ── Scaling ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("rating", "expected"), [(1, 15), (2, 20), (3, 25)])
def test_default_multipliers_scale_the_award(rating, expected):
    points, comp = _approve(ON, rating=rating)
    assert points == expected
    assert comp.points_awarded == expected
    assert comp.quality_rating == rating


def test_no_rating_pays_full_points_and_stays_unrated():
    points, comp = _approve(ON)
    assert points == 20
    assert comp.quality_rating == 0


def test_rating_is_ignored_while_the_feature_is_off():
    points, comp = _approve({}, rating=3)
    assert points == 20
    assert comp.quality_rating == 0


def test_custom_multipliers_from_settings_including_strings():
    settings = {**ON, "quality_rating_multiplier_1": "0.5", "quality_rating_multiplier_3": 2}
    assert _approve(settings, rating=1)[0] == 10
    assert _approve(settings, rating=3)[0] == 40


def test_scaling_rounds_half_up_like_the_card_preview():
    # 30 x 0.75 = 22.5: the approvals card shows 23, so the award must be 23.
    assert _approve(ON, rating=1, base=30)[0] == 23


def test_unusable_multiplier_falls_back_to_the_default():
    points, _ = _approve({**ON, "quality_rating_multiplier_3": "lots"}, rating=3)
    assert points == 25


def test_out_of_range_rating_is_ignored():
    points, comp = _approve(ON, rating=5)
    assert points == 20
    assert comp.quality_rating == 0


def test_explicit_points_are_paid_as_is_and_the_rating_recorded():
    points, comp = _approve(ON, rating=3, points=30)
    assert points == 30
    assert comp.quality_rating == 3


def test_approved_event_carries_the_rating():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _ = await _make_system(ON)
        coord.hass.bus.async_fire = MagicMock()
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            _child, _chore, completion = await _pending(coord)
            await coord.async_approve_chore(completion.id, rating=1)
        return [c.args for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == "taskmate_chore_approved"]

    fired = _run(scenario)
    assert fired and fired[0][1]["quality_rating"] == 1


# ── Reversal ─────────────────────────────────────────────────────────────


def test_undo_reverses_exactly_the_rated_amount_and_clears_the_rating():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _ = await _make_system(ON)
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child, _chore, completion = await _pending(coord)
            await coord.async_approve_chore(completion.id, rating=3)
            after_approve = coord.get_child(child.id).points
            await coord.async_undo_chore_approval(completion.id)
            kid = coord.get_child(child.id)
            undone = (kid.points, kid.total_points_earned, _stored(coord, completion.id).quality_rating)
            # Re-approving rates afresh.
            await coord.async_approve_chore(completion.id, rating=1)
            return after_approve, undone, coord.get_child(child.id).points, _stored(coord, completion.id)

    after_approve, undone, reapproved, comp = _run(scenario)
    assert after_approve == 25
    assert undone == (0, 0, 0)
    assert reapproved == 15
    assert comp.quality_rating == 1


def test_reject_after_a_rated_approval_reverses_exactly():
    async def scenario():
        import custom_components.taskmate.coord_chores as _chores
        import custom_components.taskmate.coordinator as _mod

        coord, _ = await _make_system(ON)
        coord.async_recheck_mandatory_miss = AsyncMock()
        with (
            patch.object(_mod.dt_util, "now", return_value=_now()),
            patch.object(_chores.dt_util, "now", return_value=_now()),
        ):
            child, _chore, completion = await _pending(coord)
            await coord.async_approve_chore(completion.id, rating=1)
            await coord.async_reject_chore(completion.id)
            kid = coord.get_child(child.id)
            return kid.points, kid.total_points_earned

    assert _run(scenario) == (0, 0)


def test_approve_all_applies_one_rating_to_the_batch():
    async def scenario():
        import custom_components.taskmate.coordinator as _mod

        coord, _ = await _make_system(ON)
        with patch.object(_mod.dt_util, "now", return_value=_now()):
            child = await coord.async_add_child("Alice")
            ids = []
            for name in ("A", "B"):
                chore = await coord.async_add_chore(
                    name, points=20, requires_approval=True, schedule_mode="specific_days", assigned_to=[child.id]
                )
                ids.append((await coord.async_complete_chore(chore.id, child.id)).id)
            count = await coord.async_approve_chores_bulk(ids, rating=3)
            return count, coord.get_child(child.id).points, [_stored(coord, i).quality_rating for i in ids]

    count, points, ratings = _run(scenario)
    assert count == 2
    assert points == 50
    assert ratings == [3, 3]


# ── Model ────────────────────────────────────────────────────────────────


def test_completion_round_trips_the_rating():
    comp = ChoreCompletion(chore_id="c", child_id="k", completed_at=_now(), quality_rating=2)
    assert ChoreCompletion.from_dict(comp.to_dict()).quality_rating == 2


@pytest.mark.parametrize("raw", [None, "", "abc", 0, 4, -1, True, 2.9])
def test_old_or_bad_stored_ratings_load_as_unrated(raw):
    data = {"chore_id": "c", "child_id": "k", "completed_at": _now().isoformat()}
    if raw is not None:
        data["quality_rating"] = raw
    expected = 2 if raw == 2.9 else 0
    assert ChoreCompletion.from_dict(data).quality_rating == expected


# ── Services / WebSocket schemas ─────────────────────────────────────────


def test_service_and_ws_schemas_accept_only_one_to_three():
    src = (ROOT / "custom_components" / "taskmate" / "__init__.py").read_text(encoding="utf-8")
    ws_src = (ROOT / "custom_components" / "taskmate" / "websocket.py").read_text(encoding="utf-8")
    rule = 'vol.Optional("rating"): vol.All(vol.Coerce(int), vol.Range(min=1, max=3))'
    assert src.count(rule) == 2  # approve_chore + approve_all_chores
    assert ws_src.count(rule) == 2


def test_settings_are_accepted_and_persisted():
    from custom_components.taskmate import websocket as ws

    keys = {
        "quality_rating_enabled",
        "quality_rating_multiplier_1",
        "quality_rating_multiplier_2",
        "quality_rating_multiplier_3",
    }
    schema_keys = {str(k) for k in ws._UPDATE_SETTINGS_SCHEMA}
    assert keys <= schema_keys
    assert keys <= ws._SUBKEY_SETTINGS


# ── Mobile notification actions ──────────────────────────────────────────


class _StubCoordinator:
    def __init__(self, enabled: bool):
        self.async_approve_chore = AsyncMock()
        self.async_reject_chore = AsyncMock()
        self.async_approve_reward = AsyncMock()
        self.async_reject_reward = AsyncMock()
        self.quality_rating_enabled = MagicMock(return_value=enabled)


@pytest.fixture
async def notif(hass):
    storage = TaskMateStorage(hass, "quality")
    await storage.async_load()
    storage.add_completion(ChoreCompletion(chore_id="cho1", child_id="kid1", completed_at=_now(), id="completion-123"))
    storage.add_reward_claim(RewardClaim(reward_id="rw1", child_id="kid1", claimed_at=_now(), id="claim-456"))
    n = NotificationCoordinator(hass, storage)
    n.coordinator = _StubCoordinator(enabled=True)
    return n


async def _push_actions(n, hass, type_id, entry_id):
    hass.services.async_call = AsyncMock()
    hass.bus.async_fire = MagicMock()
    p = ParentRecipient(name="John", notify_service="notify.mobile_app_johns_iphone")
    n.storage.upsert_parent_recipient(p)
    n.storage.set_notification_master(type_id, True)
    n.storage.set_notification_route(type_id, p.id, NotificationRoute(enabled=True))
    await n.fire(type_id, {"entry_id": entry_id, "child_name": "M", "chore_name": "Bin", "reward_name": "Toy"})
    call = next(c for c in hass.services.async_call.call_args_list if c[0][0] == "notify")
    return [a["action"] for a in call[0][2]["data"]["actions"]]


@pytest.mark.asyncio
async def test_rated_push_offers_three_ratings_then_reject(notif, hass):
    actions = await _push_actions(notif, hass, "pending_chore_approval", "completion-123")
    assert actions == [
        "TASKMATE_RATE_1_completion-123",
        "TASKMATE_RATE_2_completion-123",
        "TASKMATE_RATE_3_completion-123",
        "TASKMATE_REJECT_completion-123",
    ]


@pytest.mark.asyncio
async def test_push_keeps_the_original_action_ids_when_off(notif, hass):
    notif.coordinator.quality_rating_enabled.return_value = False
    actions = await _push_actions(notif, hass, "pending_chore_approval", "completion-123")
    assert actions == ["TASKMATE_APPROVE_completion-123", "TASKMATE_REJECT_completion-123"]


@pytest.mark.asyncio
async def test_reward_push_is_never_rated(notif, hass):
    actions = await _push_actions(notif, hass, "pending_reward_claim", "claim-456")
    assert actions == ["TASKMATE_APPROVE_claim-456", "TASKMATE_REJECT_claim-456"]


def _evt(action: str):
    class _E:
        data = {"action": action}

    return _E()


@pytest.mark.asyncio
async def test_rate_action_approves_with_that_rating(notif):
    await notif.handle_mobile_action(_evt("TASKMATE_RATE_3_completion-123"))
    notif.coordinator.async_approve_chore.assert_awaited_once_with("completion-123", rating=3)


@pytest.mark.asyncio
async def test_plain_approve_action_still_works_with_ratings_on(notif):
    await notif.handle_mobile_action(_evt("TASKMATE_APPROVE_completion-123"))
    notif.coordinator.async_approve_chore.assert_awaited_once_with("completion-123")


@pytest.mark.asyncio
async def test_malformed_rate_action_is_dropped(notif):
    await notif.handle_mobile_action(_evt("TASKMATE_RATE_x_completion-123"))
    notif.coordinator.async_approve_chore.assert_not_called()


# ── Insights report ──────────────────────────────────────────────────────


def test_quality_report_averages_rated_approvals_only():
    async def scenario():
        import custom_components.taskmate.coord_reports as _reports
        import custom_components.taskmate.coordinator as _mod

        coord, storage = await _make_system(ON)
        with (
            patch.object(_mod.dt_util, "now", return_value=_now()),
            patch.object(_reports.dt_util, "now", return_value=_now()),
        ):
            alice = await coord.async_add_child("Alice")
            bob = await coord.async_add_child("Bob")
            dishes = await coord.async_add_chore("Dishes", points=10)
            bins = await coord.async_add_chore("Bins", points=10)
            for child, chore, rating in (
                (alice, dishes, 3),
                (alice, bins, 1),
                (alice, bins, 0),  # unrated: excluded from the average
                (bob, dishes, 2),
            ):
                storage.add_completion(
                    ChoreCompletion(
                        chore_id=chore.id,
                        child_id=child.id,
                        completed_at=_now(),
                        approved=True,
                        quality_rating=rating,
                    )
                )
            return coord.quality_report(7)

    report = _run(scenario)
    assert report["enabled"] is True
    assert report["total_completions"] == 4
    assert report["rated_completions"] == 3
    assert report["average"] == 2.0
    kids = {r["name"]: r for r in report["children"]}
    assert kids["Alice"]["average"] == 2.0
    assert kids["Alice"]["rated"] == 2 and kids["Alice"]["total"] == 3
    assert kids["Alice"]["counts"] == {"1": 1, "2": 0, "3": 1}
    assert kids["Bob"]["average"] == 2.0
    chores = {r["name"]: r for r in report["chores"]}
    assert chores["Dishes"]["average"] == 2.5
    assert chores["Bins"]["average"] == 1.0


# ── Sensor attributes ────────────────────────────────────────────────────


def test_pending_approvals_sensor_publishes_multipliers_only_when_enabled():
    from custom_components.taskmate.sensor import PendingApprovalsSensor

    def attrs(enabled):
        sensor = object.__new__(PendingApprovalsSensor)
        coordinator = MagicMock()
        coordinator.data = {"pending_completions": [], "pending_reward_claims": []}
        coordinator.mandatory_misses_state.return_value = []
        coordinator.quality_rating_enabled.return_value = enabled
        coordinator.quality_rating_multipliers.return_value = {1: 0.75, 2: 1.0, 3: 1.25}
        sensor.coordinator = coordinator
        return sensor.extra_state_attributes

    assert "quality_rating" not in attrs(False)
    assert attrs(True)["quality_rating"] == {"multipliers": [0.75, 1.0, 1.25]}


def test_recent_completions_carry_the_rating_only_when_rated():
    from custom_components.taskmate.models import Chore
    from custom_components.taskmate.sensor import _build_recent_completions

    chore = Chore(name="Dishes", points=10, id="ch1")
    rated = ChoreCompletion(chore_id="ch1", child_id="k", completed_at=_now(), approved=True, quality_rating=3)
    plain = ChoreCompletion(chore_id="ch1", child_id="k", completed_at=_now(), approved=True)
    common = {"child_lookup": {}, "chore_lookup": {"ch1": chore}, "all_completions": [rated, plain]}
    rows = {r["completion_id"]: r for r in _build_recent_completions(common)}
    assert rows[rated.id]["rating"] == 3
    assert "rating" not in rows[plain.id]


# ── Frontend wiring (both render paths) ──────────────────────────────────


def _method_body(src: str, name: str) -> str:
    m = re.search(rf"\n  (?:async )?{name}\([^)]*\) \{{(.*?)\n  \}}\n", src, re.S)
    assert m, f"{name} not found"
    return m.group(1)


def test_approvals_card_draws_the_picker_in_every_design():
    src = (WWW / "taskmate-approvals-card.js").read_text(encoding="utf-8")
    # Classic rows and the designed rows (playroom/console/cleanpro/accessible/
    # graphite all build their actions through _apActionPair) both carry it.
    assert "_renderStars(" in _method_body(src, "_renderApprovalItem")
    assert "_renderStars(" in _method_body(src, "_apActionPair")  # playroom/cleanpro/accessible/graphite
    assert "_renderStars(" in _method_body(src, "_apConsole")  # console draws it under the subtitle
    assert "_renderStars(" in _method_body(src, "_renderReview")
    # And the rating reaches the service call.
    assert "rating" in _method_body(src, "_handleApprove")
    assert "rating" in _method_body(src, "_confirmReview")


def test_activity_card_shows_the_rating_in_both_render_paths():
    src = (WWW / "taskmate-activity-card.js").read_text(encoding="utf-8")
    assert "_ratingStars(item)" in _method_body(src, "_renderItem")
    assert "_ratingStars(item)" in _method_body(src, "_describeEvent")
    assert "r.stars" in _method_body(src, "_designConsole")  # console renders `plain`, not `text`


def test_panel_wires_the_picker_settings_and_report():
    src = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")
    assert 'data-act="rate-chore"' in src
    assert 'data-setting="quality_rating_enabled"' in src
    for n in (1, 2, 3):
        assert f'data-setting="quality_rating_multiplier_{n}"' in src
    assert "taskmate/reports/quality" in src


def test_every_new_string_is_in_every_locale():
    keys = [
        "panel.settings_quality_rating_label",
        "panel.settings_quality_rating_hint",
        "panel.settings_quality_rating_multipliers_label",
        "panel.settings_quality_rating_multipliers_hint",
        "panel.rating_label",
        "panel.rating_star_title",
        "panel.insights_view_quality",
        "panel.insights_quality_title",
        "panel.insights_quality_intro",
        "panel.insights_quality_none",
        "panel.insights_quality_overall",
        "panel.insights_quality_by_child",
        "panel.insights_quality_by_chore",
        "panel.insights_quality_col_average",
        "panel.insights_quality_col_rated",
        "panel.insights_quality_disabled",
        "approvals.rating_label",
        "approvals.rating_star_title",
        "activity.rated",
    ]
    for path in sorted((WWW / "locales").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = [k for k in keys if not data.get(k)]
        assert missing == [], f"{path.name} is missing {missing}"
