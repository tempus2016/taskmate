"""Help requests, moods, sick days, weekly goals and make-it-right penalties."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate.models import Penalty

from .test_completion_eligibility import _make_system, _now, run


def _family(**chore_fields):
    coord, storage, mod = _make_system()
    notifications = AsyncMock()
    notifications._has_outstanding_chores_today = lambda _cid: True
    coord.notifications = notifications
    coord.hass.bus = MagicMock()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Vaiha"))
        chore = run(coord.async_add_chore("Tidy room", points=5, requires_approval=True, schedule_mode="specific_days"))
    for key, value in chore_fields.items():
        setattr(chore, key, value)
    storage.update_chore(chore)
    return coord, storage, mod, kid, chore


def _at(mod, when=None):
    when = when or _now()
    return patch.object(mod.dt_util, "now", return_value=when)


def _fired(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


class TestHelp:
    def test_request_notifies_parents_and_shows_on_the_card(self):
        coord, storage, mod, kid, chore = _family()
        with _at(mod), patch("custom_components.taskmate.coord_wellbeing.dt_util.now", return_value=_now()):
            run(coord.async_request_help(kid.id, chore.id, "can't reach the shelf"))
            assert [r["chore_id"] for r in coord.open_help_requests(kid.id)] == [chore.id]
        type_id, ctx = coord.notifications.fire.call_args.args
        assert type_id == "help_requested"
        assert ctx["chore_name"] == "Tidy room" and "shelf" in ctx["message_text"]

    def test_second_tap_within_ten_minutes_is_refused(self):
        coord, _storage, mod, kid, chore = _family()
        with patch("custom_components.taskmate.coord_wellbeing.dt_util.now", return_value=_now()):
            run(coord.async_request_help(kid.id, chore.id))
            with pytest.raises(ValueError, match="on its way"):
                run(coord.async_request_help(kid.id, chore.id))

    def test_answering_closes_it_and_old_requests_lapse(self):
        coord, _storage, mod, kid, chore = _family()
        path = "custom_components.taskmate.coord_wellbeing.dt_util.now"
        with patch(path, return_value=_now()):
            req = run(coord.async_request_help(kid.id, chore.id))
            assert run(coord.async_answer_help(req["id"])) is True
            assert coord.open_help_requests(kid.id) == []
            run(coord.async_request_help(kid.id, chore.id))
        with patch(path, return_value=_now() + dt.timedelta(hours=3)):
            assert coord.open_help_requests(kid.id) == []


class TestMood:
    def test_one_mood_per_day_and_a_report(self):
        coord, _storage, mod, kid, _chore = _family()
        path = "custom_components.taskmate.coord_wellbeing.dt_util"
        with patch(f"{path}.now", return_value=_now()), patch(f"{path}.as_local", side_effect=lambda d: d):
            run(coord.async_log_mood(kid.id, "good"))
            run(coord.async_log_mood(kid.id, "great"))
            assert coord.mood_on(kid.id) == "great"
            report = coord.mood_report(7)
        row = report["children"][0]
        assert row["logged"] == 1 and row["counts"]["great"] == 1
        assert row["series"][-1] == {"date": _now().date().isoformat(), "mood": "great"}

    def test_a_low_mood_can_notify_a_parent(self):
        coord, _storage, mod, kid, _chore = _family()
        with patch("custom_components.taskmate.coord_wellbeing.dt_util.now", return_value=_now()):
            run(coord.async_log_mood(kid.id, "sad"))
        assert coord.notifications.fire.call_args.args[0] == "mood_low"
        assert _fired(coord, "taskmate_mood_logged")[0]["mood"] == "sad"

    def test_unknown_mood_is_refused(self):
        coord, _storage, _mod, kid, _chore = _family()
        with pytest.raises(ValueError):
            run(coord.async_log_mood(kid.id, "meh"))


class TestSickDay:
    def test_hides_chores_and_freezes_the_day(self):
        coord, storage, mod, kid, chore = _family()
        with _at(mod), patch("custom_components.taskmate.coord_sick.dt_util.now", return_value=_now()):
            assert coord.is_chore_available_for_child(chore, kid.id) is True
            run(coord.async_set_sick_day(kid.id))
            assert coord.is_sick_day(kid.id)
            assert coord.is_chore_available_for_child(chore, kid.id) is False
        assert _fired(coord, "taskmate_sick_day")[0]["sick"] is True

    def test_a_sick_day_never_counts_as_missed(self):
        coord, storage, mod, kid, _chore = _family()
        yesterday = _now().date() - dt.timedelta(days=1)
        with patch("custom_components.taskmate.coord_sick.dt_util.now", return_value=_now()):
            run(coord.async_set_sick_day(kid.id, yesterday))
        two_days_ago = (_now().date() - dt.timedelta(days=2)).isoformat()
        assert coord._unprotected_missed_days(two_days_ago, _now().date(), storage.get_child(kid.id)) == []

    def test_taken_back(self):
        coord, _storage, _mod, kid, _chore = _family()
        with patch("custom_components.taskmate.coord_sick.dt_util.now", return_value=_now()):
            run(coord.async_set_sick_day(kid.id))
            run(coord.async_set_sick_day(kid.id, sick=False))
            assert not coord.is_sick_day(kid.id)

    def test_far_future_is_refused(self):
        coord, _storage, _mod, kid, _chore = _family()
        with patch("custom_components.taskmate.coord_sick.dt_util.now", return_value=_now()), pytest.raises(ValueError):
            run(coord.async_set_sick_day(kid.id, _now().date() + dt.timedelta(days=60)))


class TestWeeklyGoal:
    def _on(self, storage, bonus=15):
        storage.set_setting("weekly_goal_enabled", True)
        storage.set_setting("weekly_goal_bonus", bonus)

    def test_off_by_default(self):
        coord, _storage, _mod, kid, _chore = _family()
        assert coord.weekly_goal_state(kid.id) is None
        with pytest.raises(ValueError):
            run(coord.async_set_weekly_goal(kid.id, 50))

    def test_reaching_the_goal_pays_the_bonus_once(self):
        coord, storage, mod, kid, chore = _family(requires_approval=False)
        self._on(storage)
        goals = "custom_components.taskmate.coord_goals.dt_util"
        with _at(mod), patch(f"{goals}.now", return_value=_now()), patch(f"{goals}.as_local", side_effect=lambda d: d):
            run(coord.async_set_weekly_goal(kid.id, 5))
            assert storage.get_child(kid.id).points == 0
            run(coord.async_complete_chore(chore.id, kid.id))
            assert run(coord.async_check_weekly_goals()) == 1
            assert run(coord.async_check_weekly_goals()) == 0
            state = coord.weekly_goal_state(kid.id)
        assert storage.get_child(kid.id).points == 5 + 15
        assert state["reached"] is True and state["earned"] == 5
        assert coord.notifications.fire.call_args.args[0] == "weekly_goal_reached"

    def test_zero_clears_the_goal(self):
        coord, storage, _mod, kid, _chore = _family()
        self._on(storage)
        with patch("custom_components.taskmate.coord_goals.dt_util.now", return_value=_now()):
            run(coord.async_set_weekly_goal(kid.id, 80))
            run(coord.async_set_weekly_goal(kid.id, 0))
            assert coord.weekly_goal_state(kid.id)["target"] == 0


class TestMakeItRight:
    def _penalised(self, percent=50, **chore_fields):
        coord, storage, mod, kid, chore = _family(**chore_fields)
        storage.update_child(type(kid)(**{**kid.__dict__, "points": 40}))
        penalty = Penalty(name="Slammed the door", points=10, redemption_chore_id=chore.id, redemption_percent=percent)
        storage.add_penalty(penalty)
        red = "custom_components.taskmate.coord_redemptions.dt_util"
        with _at(mod), patch(f"{red}.now", return_value=_now()), patch(f"{red}.as_local", side_effect=lambda d: d):
            run(coord.async_apply_penalty(penalty.id, kid.id))
        return coord, storage, mod, kid, chore, red

    def test_applying_offers_the_chore(self):
        coord, storage, mod, kid, chore, red = self._penalised()
        with patch(f"{red}.now", return_value=_now()), patch(f"{red}.as_local", side_effect=lambda d: d):
            offers = coord.open_redemptions(kid.id)
        assert storage.get_child(kid.id).points == 30
        assert len(offers) == 1 and offers[0]["points"] == 5 and offers[0]["chore_id"] == chore.id

    def test_offer_makes_an_unscheduled_chore_doable(self):
        coord, storage, mod, kid, chore, red = self._penalised(due_days=["sunday"])
        with _at(mod), patch(f"{red}.now", return_value=_now()), patch(f"{red}.as_local", side_effect=lambda d: d):
            assert coord._is_chore_completable_by_child(chore, kid.id) is True

    def test_approval_pays_the_refund_and_undo_takes_it_back(self):
        coord, storage, mod, kid, chore, red = self._penalised(percent=100)
        with _at(mod), patch(f"{red}.now", return_value=_now()), patch(f"{red}.as_local", side_effect=lambda d: d):
            comp = run(coord.async_complete_chore(chore.id, kid.id))
            run(coord.async_approve_chore(comp.id))
            assert storage.get_child(kid.id).points == 30 + 5 + 10
            assert coord.open_redemptions(kid.id) == []
            assert coord.notifications.fire.call_args.args[0] == "penalty_redeemed"
            run(coord.async_undo_chore_approval(comp.id))
            assert storage.get_child(kid.id).points == 30
            assert len(coord.open_redemptions(kid.id)) == 1

    def test_offer_expires(self):
        coord, _storage, _mod, kid, _chore, red = self._penalised()
        later = _now() + dt.timedelta(days=2)
        with patch(f"{red}.now", return_value=later), patch(f"{red}.as_local", side_effect=lambda d: d):
            assert coord.open_redemptions(kid.id) == []

    def test_penalty_without_a_chore_offers_nothing(self):
        coord, storage, mod, kid, _chore = _family()
        penalty = Penalty(name="Rude", points=3)
        storage.add_penalty(penalty)
        with _at(mod):
            run(coord.async_apply_penalty(penalty.id, kid.id))
        assert storage.get_section("penalty_redemptions", list) == []

    def test_penalty_fields_round_trip(self):
        p = Penalty.from_dict(Penalty(name="x", points=4, redemption_chore_id="c", redemption_percent=150).to_dict())
        assert p.redemption_chore_id == "c" and p.redemption_percent == 100 and p.redemption_days == 1


def test_removing_a_child_forgets_them_everywhere():
    coord, storage, mod, kid, chore = _family()
    storage.get_section("moods", dict)[kid.id] = {"2024-03-20": "good"}
    storage.get_section("sick_days", dict)[kid.id] = ["2024-03-20"]
    storage.get_section("help_requests", list).append({"child_id": kid.id, "id": "h"})
    storage.remove_child_from_sections(kid.id)
    assert storage.get_section("moods", dict) == {}
    assert storage.get_section("sick_days", dict) == {}
    assert storage.get_section("help_requests", list) == []


def test_redemption_compares_instants_across_time_zones():
    """The offer is stamped in local time, the completion in UTC (live bug)."""
    import asyncio

    coord, storage, mod, kid, chore = _family()
    local = dt.timezone(dt.timedelta(hours=1))
    offer = {
        "id": "o1",
        "child_id": kid.id,
        "chore_id": chore.id,
        "penalty_name": "Bike",
        "points": 6,
        "created_at": dt.datetime(2024, 3, 20, 23, 10, tzinfo=local).isoformat(),
        "expires": "2024-03-21",
        "status": "open",
    }
    storage.get_section("penalty_redemptions", list).append(offer)
    completion = MagicMock(bonus_subtask_id="", id="c1", completed_at=dt.datetime(2024, 3, 20, 22, 30, tzinfo=dt.UTC))
    red = "custom_components.taskmate.coord_redemptions.dt_util"
    with (
        patch(f"{red}.now", return_value=dt.datetime(2024, 3, 20, 22, 31, tzinfo=dt.UTC)),
        patch(f"{red}.as_local", side_effect=lambda d: d),
    ):
        asyncio.run(coord._async_redeem_penalty(chore, storage.get_child(kid.id), completion))
    assert offer["status"] == "redeemed"
