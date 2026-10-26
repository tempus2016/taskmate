"""Whole-app hardening, 25 October 2026: nothing automatic prices a child's
own number; list-driven chores are bounded; undoing a penalty settles its
make-it-right offer; derived bonuses follow approvals, not submissions;
savings can't dodge expiry or decay; a timed stop pays once.

These drive the real coordinator against real storage.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate import notify_strings
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, ChoreCompletion, Penalty, PointsTransaction, TimedSession

from .test_completion_eligibility import _make_system, _now, run
from .test_family_care import _at, _family

UTC = dt.timezone.utc
BINS = "custom_components.taskmate.coord_bin_days.dt_util"


def _completion(storage, completion_id):
    return next((c for c in storage.get_completions() if c.id == completion_id), None)


# ── 1. an uncapped quantity is the child's own number ───────────────────────


class TestUncappedQuantityNeedsAParent:
    def _system(self):
        coord, storage, mod, kid, chore = _family(requires_approval=False, quantity_unit="pages")
        coord.badges = None
        coord._celebrate = AsyncMock()
        with _at(mod):
            big = run(coord.async_add_child("Leo"))
            capped = run(coord.async_add_chore("Laps", points=2, requires_approval=True))
        capped.quantity_unit = "laps"
        capped.quantity_max = 10
        storage.update_chore(capped)
        with _at(mod):
            open_comp = run(coord.async_complete_chore(chore.id, kid.id, quantity=500))
            capped_comp = run(coord.async_complete_chore(capped.id, kid.id, quantity=4))
        assert open_comp.approved is False and capped_comp.approved is False
        return coord, storage, mod, kid, big, open_comp, capped_comp

    def test_auto_approve_leaves_an_uncapped_quantity_for_a_parent(self):
        coord, storage, mod, kid, _big, open_comp, capped_comp = self._system()
        storage.set_setting("auto_approve_hours", 1)
        with _at(mod, _now() + dt.timedelta(hours=2)):
            assert [c.id for c in coord.overdue_completions()] == [capped_comp.id]
            assert run(coord.async_auto_approve_overdue()) == 1
        assert storage.get_child(kid.id).points == 8
        assert _completion(storage, open_comp.id).approved is False

    def test_a_sibling_check_never_offers_an_uncapped_quantity(self):
        coord, storage, mod, _kid, big, open_comp, capped_comp = self._system()
        storage.set_setting("sibling_check_enabled", True)
        storage.set_setting("sibling_check_pairs", {big.id: [open_comp.child_id]})
        with _at(mod):
            rows = coord.sibling_checks_for_child(big.id)
            assert [r["completion_id"] for r in rows] == [capped_comp.id]
            with pytest.raises(ValueError, match="already been checked"):
                run(coord.async_sibling_check(big.id, open_comp.id, "done"))
        assert _completion(storage, open_comp.id).approved is False

    def test_an_overturned_appeal_pays_exactly_what_the_record_shows(self):
        coord, storage, mod, kid, chore = _family(requires_approval=False, quantity_unit="pages")
        coord.badges = None
        coord._celebrate = AsyncMock()
        storage.set_setting("appeals_enabled", True)
        with _at(mod):
            comp = run(coord.async_complete_chore(chore.id, kid.id, quantity=50))
            run(coord.async_reject_chore(comp.id, reason="That's a lot of pages"))
            (item,) = coord.appealable_for_child(kid.id)
            appeal = run(coord.async_appeal(kid.id, "chore", item["target_id"]))
            assert item["points"] == appeal["points"] == 250
            run(coord.async_decide_appeal(appeal["id"], overturn=True))
        assert storage.get_child(kid.id).points == 250


# ── 2. list-driven chores are bounded ────────────────────────────────────────


def _shopping_system(items):
    coord, storage, mod = _make_system()
    coord.hass.bus = MagicMock()
    coord.badges = None
    todo = list(items)

    async def fake_call(domain, service, data, blocking=False, return_response=False):
        if service == "get_items":
            return {data["entity_id"]: {"items": [i for i in todo if i.get("status") == "needs_action"]}}
        return None

    coord.hass.services = MagicMock()
    coord.hass.services.async_call = AsyncMock(side_effect=fake_call)
    storage.set_setting("shopping_jobs_enabled", True)
    with _at(mod):
        run(coord.async_add_child("Vaiha"))
    return coord, storage, mod


def _tagged(n):
    return [{"uid": f"u{i}", "summary": f"#tm job {i}", "status": "needs_action"} for i in range(n)]


def _jobs(storage):
    return [c for c in storage.get_chores() if c.name.startswith("🛒")]


class TestShoppingJobsAreBounded:
    def test_a_flood_of_tagged_items_raises_a_few_at_a_time_and_stops_at_the_cap(self):
        from custom_components.taskmate.coord_shopping_jobs import SHOPPING_JOBS_MAX_OPEN, SHOPPING_JOBS_MAX_PER_POLL

        assert (SHOPPING_JOBS_MAX_PER_POLL, SHOPPING_JOBS_MAX_OPEN) == (5, 10)
        coord, storage, mod = _shopping_system(_tagged(20))
        t0 = _now()
        with _at(mod, t0):
            assert run(coord.async_check_shopping_jobs()) == 5
        with _at(mod, t0 + dt.timedelta(minutes=3)):
            assert run(coord.async_check_shopping_jobs()) == 5
        with _at(mod, t0 + dt.timedelta(minutes=6)):
            assert run(coord.async_check_shopping_jobs()) == 0
        jobs = _jobs(storage)
        assert len(jobs) == 10
        assert all(c.requires_approval for c in jobs)

    def test_one_poll_saves_and_refreshes_once_however_many_chores_it_raises(self):
        coord, storage, mod = _shopping_system(_tagged(5))
        storage.async_save = AsyncMock(wraps=storage.async_save)
        coord.async_refresh.reset_mock()
        with _at(mod):
            assert run(coord.async_check_shopping_jobs()) == 5
        assert coord.async_refresh.await_count == 1
        assert storage.async_save.await_count == 1


def _bin_system(events):
    coord, storage, mod = _make_system()
    coord.hass.bus = MagicMock()
    coord.badges = None

    async def fake_call(domain, service, data, blocking=False, return_response=False):
        return {data["entity_id"]: {"events": list(events)}}

    coord.hass.services = MagicMock()
    coord.hass.services.async_call = AsyncMock(side_effect=fake_call)
    storage.set_setting("bin_day_enabled", True)
    storage.set_setting("bin_day_calendars", ["calendar.bins"])
    with _at(mod):
        run(coord.async_add_child("Vaiha"))
    return coord, storage, mod


def _bin_tick(coord, mod, when):
    with (
        _at(mod, when),
        patch(
            f"{BINS}.start_of_local_day",
            side_effect=lambda d: d.replace(hour=0, minute=0, second=0, microsecond=0),
        ),
    ):
        return run(coord.async_check_bin_days())


def _bin_chores(storage):
    return [c for c in storage.get_chores() if c.name.endswith(" out")]


class TestBinDaysAreBounded:
    def test_a_calendar_full_of_bins_raises_a_few_at_a_time_and_stops_at_the_cap(self):
        from custom_components.taskmate.coord_bin_days import BIN_DAY_MAX_OPEN, BIN_DAY_MAX_PER_POLL

        assert (BIN_DAY_MAX_PER_POLL, BIN_DAY_MAX_OPEN) == (5, 10)
        tomorrow = (_now().date() + dt.timedelta(days=1)).isoformat()
        coord, storage, mod = _bin_system([{"summary": f"Bin {i}", "start": tomorrow} for i in range(20)])
        evening = _now().replace(hour=18, minute=5)
        assert _bin_tick(coord, mod, evening) == 5
        assert _bin_tick(coord, mod, evening + dt.timedelta(minutes=16)) == 5
        assert _bin_tick(coord, mod, evening + dt.timedelta(minutes=32)) == 0
        chores = _bin_chores(storage)
        assert len(chores) == 10
        assert all(c.requires_approval for c in chores)

    def test_one_tick_refreshes_once_however_many_chores_it_raises(self):
        tomorrow = (_now().date() + dt.timedelta(days=1)).isoformat()
        coord, storage, mod = _bin_system([{"summary": f"Bin {i}", "start": tomorrow} for i in range(5)])
        storage.async_save = AsyncMock(wraps=storage.async_save)
        coord.async_refresh.reset_mock()
        assert _bin_tick(coord, mod, _now().replace(hour=18, minute=5)) == 5
        assert coord.async_refresh.await_count == 1
        assert storage.async_save.await_count == 1


# ── 3. undoing a penalty settles its make-it-right offer ────────────────────


class TestUndoingAPenaltySettlesItsOffer:
    def _penalised(self):
        coord, storage, mod, kid, chore = _family(requires_approval=False)
        coord.badges = None
        coord._celebrate = AsyncMock()
        kid.points = 40
        storage.update_child(kid)
        storage.add_penalty(Penalty(name="Slammed the door", points=10, id="pen1", redemption_chore_id=chore.id))
        with _at(mod):
            run(coord.async_apply_penalty("pen1", kid.id))
        txn = next(t for t in storage.get_points_transactions() if t.reason == "Penalty: Slammed the door")
        assert storage.get_child(kid.id).points == 30
        return coord, storage, mod, kid, chore, txn

    def test_undo_cancels_an_open_offer_so_the_chore_pays_only_its_own_points(self):
        coord, storage, mod, kid, chore, txn = self._penalised()
        with _at(mod):
            run(coord.async_undo_transaction(txn.id))
            assert storage.get_child(kid.id).points == 40
            assert coord.open_redemptions(kid.id) == []
            (offer,) = storage.get_section("penalty_redemptions", list)
            assert offer["status"] == "cancelled"
            run(coord.async_complete_chore(chore.id, kid.id))
        assert storage.get_child(kid.id).points == 45

    def test_undo_is_refused_once_the_penalty_was_earned_back(self):
        coord, storage, mod, kid, chore, txn = self._penalised()
        with _at(mod):
            run(coord.async_complete_chore(chore.id, kid.id))
            assert storage.get_child(kid.id).points == 45
            with pytest.raises(ValueError, match="earned back"):
                run(coord.async_undo_transaction(txn.id))
        assert storage.get_child(kid.id).points == 45
        assert any(t.id == txn.id for t in storage.get_points_transactions())


# ── 5. the undo deny-list and gifts ─────────────────────────────────────────


class TestUndoDenyList:
    @pytest.mark.parametrize(
        "reason",
        [
            "Raffle tickets: Saturday raffle (3)",
            "Allowance payout",
            "Made it right: Slammed the door",
            "Quest complete: Autumn clean-up",
            "Appeal: Tidy room",
            "Sibling check: Tidy room",
            "Perfect week bonus reversed (11 Mar – 17 Mar)",
            "Streak milestone reversed (7 days)",
        ],
    )
    def test_derived_rows_cannot_be_undone(self, reason):
        coord, storage, _mod, kid, _chore = _family()
        txn = PointsTransaction(child_id=kid.id, points=5, reason=reason, created_at=_now())
        storage.add_points_transaction(txn)
        with pytest.raises(ValueError, match="can't be undone"):
            run(coord.async_undo_transaction(txn.id))

    def test_a_gift_cannot_be_undone_once_the_recipient_has_spent_it(self):
        coord, storage, mod, kid, _chore = _family()
        with _at(mod):
            leo = run(coord.async_add_child("Leo"))
        kid.points = 20
        storage.update_child(kid)
        with _at(mod):
            run(coord.async_gift_points(kid.id, leo.id, 20))
            run(coord.async_remove_points(leo.id, 15, reason="Sweets"))
            gift = next(t for t in storage.get_points_transactions() if t.reason.startswith("Gift from "))
            with pytest.raises(ValueError, match="spent"):
                run(coord.async_undo_transaction(gift.id))
        assert storage.get_child(kid.id).points == 0
        assert storage.get_child(leo.id).points == 5
        assert len([t for t in storage.get_points_transactions() if t.reason.startswith("Gift")]) == 2

    def test_a_gift_still_held_can_be_undone(self):
        coord, storage, mod, kid, _chore = _family()
        with _at(mod):
            leo = run(coord.async_add_child("Leo"))
        kid.points = 20
        storage.update_child(kid)
        with _at(mod):
            run(coord.async_gift_points(kid.id, leo.id, 20))
            gift = next(t for t in storage.get_points_transactions() if t.reason.startswith("Gift from "))
            run(coord.async_undo_transaction(gift.id))
        assert storage.get_child(kid.id).points == 20
        assert storage.get_child(leo.id).points == 0


# ── 8. a timed stop pays once ────────────────────────────────────────────────


class TestTimedStopPaysOnce:
    def test_two_stops_landing_together_pay_once(self):
        now = dt.datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
        start = now - dt.timedelta(minutes=30)
        chore = Chore(
            name="Piano",
            task_type="timed",
            timed_rate_points=5,
            timed_rate_minutes=10,
            requires_approval=False,
            id="cho1",
        )
        session = TimedSession(
            chore_id="cho1",
            child_id="ch1",
            state="running",
            segments=[{"start": start.isoformat(), "end": None}],
            session_date=now.date().isoformat(),
            id="sess1",
        )
        live = {"session": session}
        coord = object.__new__(TaskMateCoordinator)
        storage = MagicMock()
        storage.get_chore = MagicMock(return_value=chore)
        storage.get_child = MagicMock(return_value=Child(name="Alice", id="ch1"))
        storage.get_active_timed_session = MagicMock(side_effect=lambda *_: live["session"])
        storage.remove_timed_session = MagicMock(side_effect=lambda _id: live.update(session=None))
        storage.get_completions = MagicMock(return_value=[])
        storage.async_save = AsyncMock()
        coord.storage = storage
        coord.async_refresh = AsyncMock()
        coord._async_notify_pending_approval = AsyncMock()

        async def slow_award(child, pts, **_kw):
            await asyncio.sleep(0)
            return pts

        coord._award_points = AsyncMock(side_effect=slow_award)

        async def both():
            return await asyncio.gather(
                coord.async_stop_timed_task("cho1", "ch1"),
                coord.async_stop_timed_task("cho1", "ch1"),
                return_exceptions=True,
            )

        with patch("custom_components.taskmate.coord_timed.dt_util.now", return_value=now):
            results = run(both())

        assert coord._award_points.await_count == 1
        assert storage.add_completion.call_count == 1
        assert sum(isinstance(r, ValueError) for r in results) == 1
        completion = storage.add_completion.call_args[0][0]
        assert completion.approved is True and completion.points_awarded == 15


# ── 9. a wish picture may not be anybody's evidence ─────────────────────────


class TestWishPhotoAdoption:
    def test_a_photo_held_by_a_half_formed_team_cannot_become_a_wish_picture(self):
        coord, storage, mod, kid, chore = _family()
        photo = "/api/taskmate/photo/" + "c" * 32 + ".jpg"
        storage.set_team_joins(chore.id, "2024-03-20", [{"child_id": "leo", "photo_url": photo}])
        adopt = AsyncMock(return_value="/api/taskmate/image/" + "d" * 32 + ".jpg")
        with (
            patch("custom_components.taskmate.coord_wishlist.images.async_adopt_photo", adopt),
            _at(mod),
            pytest.raises(ValueError, match="picture"),
        ):
            run(coord.async_add_wish(kid.id, "Skates", 40, photo_url=photo))
        adopt.assert_not_awaited()


# ── 10. an allowance payout needs the points to be there ────────────────────


class TestAllowancePayout:
    def test_a_payout_bigger_than_the_balance_is_refused(self):
        coord, storage, mod, kid, _chore = _family()
        storage.set_setting("allowance_enabled", True)
        kid.points = 5
        storage.update_child(kid)
        with _at(mod), pytest.raises(ValueError, match="only has 5"):
            run(coord.async_record_allowance_payout(kid.id, 10))
        assert storage.get_child(kid.id).points == 5
        assert storage.get_allowance_payouts() == []
        assert storage.get_points_transactions() == []


# ── 11. a template placeholder is a name, not a format spec ────────────────


class TestSafeFormatSpecs:
    def test_a_huge_width_spec_is_refused_before_it_allocates(self):
        try:
            out = notify_strings.safe_format("{child_name:>5000}", {"child_name": "Mia"})
        except ValueError:
            return
        assert len(out) < 200, "a width spec padded the output instead of being refused"

    def test_plain_placeholders_still_work(self):
        assert notify_strings.safe_format("Hi {child_name}!", {"child_name": "Mia"}) == "Hi Mia!"
        assert notify_strings.safe_format("Hi {nope}!", {"child_name": "Mia"}) == "Hi {nope}!"


# ── 4. the perfect week follows approvals ───────────────────────────────────


class TestPerfectWeekFollowsApprovals:
    # The Monday after the week of 11–17 March 2024.
    MONDAY = dt.datetime(2024, 3, 18, 0, 5, tzinfo=UTC)

    def _week(self):
        coord, storage, mod, kid, chore = _family(requires_approval=True)
        coord.badges = None
        coord._celebrate = AsyncMock()
        storage.set_setting("perfect_week_bonus", "50")
        storage.set_setting("weekend_multiplier", "1")
        storage.set_setting("streak_milestones_enabled", "false")
        comps = []
        for i in range(7):
            when = dt.datetime(2024, 3, 11 + i, 12, tzinfo=UTC)
            comp = ChoreCompletion(chore_id=chore.id, child_id=kid.id, completed_at=when, submitted_points=5)
            storage.add_completion(comp)
            comps.append(comp)
        return coord, storage, mod, kid, comps

    def _check(self, coord, mod, when):
        with _at(mod, when):
            run(coord._async_check_perfect_week())

    def test_pending_completions_earn_nothing(self):
        coord, storage, mod, kid, _comps = self._week()
        self._check(coord, mod, self.MONDAY)
        child = storage.get_child(kid.id)
        assert child.points == 0 and child.awarded_perfect_weeks == []

    def test_approving_them_later_in_the_week_still_earns_it(self):
        coord, storage, mod, kid, comps = self._week()
        self._check(coord, mod, self.MONDAY)
        with _at(mod, self.MONDAY + dt.timedelta(hours=9)):
            for comp in comps:
                run(coord.async_approve_chore(comp.id))
        # Tuesday night's run picks it up: the check is nightly, not Monday-only.
        self._check(coord, mod, self.MONDAY + dt.timedelta(days=1))
        child = storage.get_child(kid.id)
        assert child.points == 7 * 5 + 50 and child.awarded_perfect_weeks == ["2024-03-11"]
        self._check(coord, mod, self.MONDAY + dt.timedelta(days=2))
        assert storage.get_child(kid.id).points == 7 * 5 + 50

    def test_un_approving_a_day_claws_the_bonus_back(self):
        coord, storage, mod, kid, comps = self._week()
        with _at(mod, self.MONDAY):
            for comp in comps:
                run(coord.async_approve_chore(comp.id))
        self._check(coord, mod, self.MONDAY)
        assert storage.get_child(kid.id).points == 85
        with _at(mod, self.MONDAY + dt.timedelta(days=1)):
            run(coord.async_undo_chore_approval(comps[3].id))
        child = storage.get_child(kid.id)
        assert child.points == 30 and child.total_points_earned == 30 and child.career_score == 30
        assert child.awarded_perfect_weeks == []
        (reversal,) = [
            t for t in storage.get_points_transactions() if t.reason.startswith("Perfect week bonus reversed")
        ]
        assert reversal.points == -50
        # Re-approving the day lets the nightly check pay the week again, once.
        with _at(mod, self.MONDAY + dt.timedelta(days=1, hours=9)):
            run(coord.async_approve_chore(comps[3].id))
        self._check(coord, mod, self.MONDAY + dt.timedelta(days=2))
        assert storage.get_child(kid.id).points == 85

    def test_rejecting_an_approved_day_claws_the_bonus_back_too(self):
        # A parent can reject work they already approved; that is the other
        # way a paid week stops qualifying.
        coord, storage, mod, kid, comps = self._week()
        with _at(mod, self.MONDAY):
            for comp in comps:
                run(coord.async_approve_chore(comp.id))
        self._check(coord, mod, self.MONDAY)
        assert storage.get_child(kid.id).points == 85
        with _at(mod, self.MONDAY + dt.timedelta(days=1)):
            run(coord.async_reject_chore(comps[3].id))
        child = storage.get_child(kid.id)
        assert child.awarded_perfect_weeks == []
        assert child.points == 30 and child.total_points_earned == 30
        assert any(t.reason.startswith("Perfect week bonus reversed") for t in storage.get_points_transactions())


# ── 6. a child's weekly goal can't pay itself ───────────────────────────────


class TestWeeklyGoalSelfPay:
    def _on(self, bonus=10, **chore_fields):
        coord, storage, mod, kid, chore = _family(requires_approval=False, **chore_fields)
        coord.badges = None
        storage.set_setting("weekly_goal_enabled", True)
        storage.set_setting("weekly_goal_bonus", bonus)
        return coord, storage, mod, kid, chore

    def test_a_child_cannot_set_a_target_below_the_bonus(self):
        coord, storage, mod, kid, _chore = self._on()
        with _at(mod):
            with pytest.raises(ValueError, match="at least 10"):
                run(coord.async_set_weekly_goal(kid.id, 5))
            assert coord.weekly_goal_state(kid.id)["target"] == 0
            run(coord.async_set_weekly_goal(kid.id, 10))
            run(coord.async_set_weekly_goal(kid.id, 0))
            # A parent may set whatever they like.
            run(coord.async_set_weekly_goal(kid.id, 5, as_parent=True))
            assert coord.weekly_goal_state(kid.id)["target"] == 5

    def test_a_child_cannot_move_the_target_once_this_weeks_bonus_is_paid(self):
        coord, storage, mod, kid, chore = self._on(daily_limit=3)
        with _at(mod):
            run(coord.async_set_weekly_goal(kid.id, 10))
            run(coord.async_complete_chore(chore.id, kid.id))
            run(coord.async_complete_chore(chore.id, kid.id))
            assert run(coord.async_check_weekly_goals()) == 1
            assert storage.get_child(kid.id).points == 20
            with pytest.raises(ValueError, match="already been reached"):
                run(coord.async_set_weekly_goal(kid.id, 100))
            with pytest.raises(ValueError, match="already been reached"):
                run(coord.async_set_weekly_goal(kid.id, 0))
            # Re-saving the same target is harmless; a parent may still change it.
            run(coord.async_set_weekly_goal(kid.id, 10))
            run(coord.async_set_weekly_goal(kid.id, 100, as_parent=True))
            assert coord.weekly_goal_state(kid.id)["target"] == 100
        assert storage.get_child(kid.id).points == 20

    def test_the_reversal_judges_the_target_the_bonus_was_paid_for(self):
        coord, storage, mod, kid, chore = self._on(daily_limit=3)
        with _at(mod):
            run(coord.async_set_weekly_goal(kid.id, 10))
            run(coord.async_complete_chore(chore.id, kid.id))
            second = run(coord.async_complete_chore(chore.id, kid.id))
            assert run(coord.async_check_weekly_goals()) == 1
            goal = storage.get_section("weekly_goals", dict)[kid.id]
            assert goal["paid_target"] == 10
            # Lowering the target afterwards must not keep a bonus the week no longer earns.
            run(coord.async_set_weekly_goal(kid.id, 5, as_parent=True))
            run(coord.async_reject_chore(second.id))
        assert storage.get_child(kid.id).points == 5
        goal = storage.get_section("weekly_goals", dict)[kid.id]
        assert "reached_week" not in goal and "paid_target" not in goal
        assert any(t.reason == "Weekly goal reversed (10)" for t in storage.get_points_transactions())


# ── 7. wish savings keep their expiry clock and decay like a balance ────────


def _lots(storage, child_id):
    return storage.get_section("points_expiry", dict)[child_id]["lots"]


class TestWishSavingsAndExpiry:
    def _system(self):
        coord, storage, mod, kid, _chore = _family()
        coord.badges = None
        kid.points = 100
        storage.update_child(kid)
        storage.set_setting("points_expiry_enabled", True)
        storage.set_setting("points_expiry_days", 30)
        with _at(mod):
            wish = run(coord.async_add_wish(kid.id, "Lego", target=500))
            run(coord.async_approve_wish(wish.id))
            run(coord.async_check_points_expiry())
        assert _lots(storage, kid.id) == [{"d": "2024-03-20", "n": 100}]
        return coord, storage, mod, kid, wish

    def test_moving_in_and_back_out_keeps_the_original_lot_date(self):
        coord, storage, mod, kid, wish = self._system()
        with _at(mod, _now() + dt.timedelta(days=10)):
            run(coord.async_move_points_to_wish(wish.id, kid.id, 60))
            run(coord.async_check_points_expiry())
            assert _lots(storage, kid.id) == [{"d": "2024-03-20", "n": 40}]
            assert storage.get_wish(wish.id).saved == 60
            run(coord.async_take_points_from_wish(wish.id, kid.id, 60))
            run(coord.async_check_points_expiry())
            assert _lots(storage, kid.id) == [{"d": "2024-03-20", "n": 100}]
        with _at(mod, _now() + dt.timedelta(days=31)):
            assert run(coord.async_check_points_expiry()) == 100
        assert storage.get_child(kid.id).points == 0

    def test_a_partial_take_back_returns_the_oldest_lots_first(self):
        coord, storage, mod, kid, wish = self._system()
        with _at(mod, _now() + dt.timedelta(days=5)):
            child = storage.get_child(kid.id)
            child.points = 150
            storage.update_child(child)
            run(coord.async_check_points_expiry())
            assert _lots(storage, kid.id) == [{"d": "2024-03-20", "n": 100}, {"d": "2024-03-25", "n": 50}]
            run(coord.async_move_points_to_wish(wish.id, kid.id, 120))
            assert storage.get_wish(wish.id).saved_lots == [{"d": "2024-03-20", "n": 100}, {"d": "2024-03-25", "n": 20}]
            run(coord.async_take_points_from_wish(wish.id, kid.id, 30))
            run(coord.async_check_points_expiry())
        assert _lots(storage, kid.id) == [{"d": "2024-03-20", "n": 30}, {"d": "2024-03-25", "n": 30}]
        assert storage.get_wish(wish.id).saved_lots == [{"d": "2024-03-20", "n": 70}, {"d": "2024-03-25", "n": 20}]


class TestWishSavingsDecay:
    def test_weekly_decay_reduces_wish_savings_too(self):
        coord, storage, mod, kid, _chore = _family()
        coord.badges = None
        kid.points = 100
        storage.update_child(kid)
        storage.set_setting("points_decay_enabled", True)
        storage.set_setting("points_decay_period", "weekly")
        storage.set_setting("points_decay_percent", "10")
        with _at(mod):
            wish = run(coord.async_add_wish(kid.id, "Lego", target=500))
            run(coord.async_approve_wish(wish.id))
            run(coord.async_move_points_to_wish(wish.id, kid.id, 50))
        with _at(mod, dt.datetime(2024, 3, 25, 0, 5, tzinfo=UTC)):
            run(coord._async_decay_points())
        assert storage.get_child(kid.id).points == 45
        assert storage.get_wish(wish.id).saved == 45
        (txn,) = [t for t in storage.get_points_transactions() if t.reason.startswith("Points decay")]
        assert txn.points == -5
        assert "5 from wish savings" in txn.reason
