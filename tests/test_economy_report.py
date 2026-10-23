"""Economy insight: points earned vs spent per week, and the inflation warning."""

from __future__ import annotations

import datetime as dt
from unittest.mock import patch

from custom_components.taskmate.coord_reports import ECONOMY_MIN_EARNED, ECONOMY_RATIO, ECONOMY_WEEKS
from custom_components.taskmate.models import ChoreCompletion, PointsTransaction, RewardClaim

from .test_completion_eligibility import _make_system, _now, run

REPORTS = "custom_components.taskmate.coord_reports.dt_util.now"


def _system():
    coord, storage, mod = _make_system()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Malia"))
        with patch("custom_components.taskmate.coord_rewards.dt_util.now", return_value=_now()):
            cinema = run(coord.async_add_reward("Cinema trip", cost=200))
            xbox = run(coord.async_add_reward("30 min Xbox", cost=40))
    return coord, storage, kid, cinema, xbox


def _earn(storage, kid, days_ago, points):
    storage.add_completion(
        ChoreCompletion(
            chore_id="c",
            child_id=kid.id,
            completed_at=_now() - dt.timedelta(days=days_ago),
            approved=True,
            points_awarded=points,
        )
    )


def _spend(storage, kid, reward, days_ago, cost=None):
    when = _now() - dt.timedelta(days=days_ago)
    storage.add_reward_claim(
        RewardClaim(
            reward_id=reward.id,
            child_id=kid.id,
            claimed_at=when,
            approved=True,
            approved_at=when,
            approved_cost=cost,
        )
    )


def _report(coord):
    with patch(REPORTS, return_value=_now()):
        return coord.economy_report()


def test_weeks_bucket_earned_and_spent_with_the_latest_ending_today():
    coord, storage, kid, cinema, xbox = _system()
    _earn(storage, kid, 0, 10)  # this week
    _earn(storage, kid, 7, 20)  # last week
    _earn(storage, kid, 56, 99)  # before the window
    _spend(storage, kid, xbox, 1)  # current cost (40)
    _spend(storage, kid, cinema, 8, cost=150)  # recorded price wins
    storage.add_points_transaction(
        PointsTransaction(child_id=kid.id, points=5, reason="Bonus: tidy", created_at=_now())
    )
    storage.add_points_transaction(
        PointsTransaction(child_id=kid.id, points=80, reason="Pool refund (reward deleted): X", created_at=_now())
    )
    report = _report(coord)
    weeks = report["weeks"]
    assert len(weeks) == ECONOMY_WEEKS
    assert weeks[-1]["end"] == _now().date().isoformat()
    assert [w["earned"] for w in weeks[-2:]] == [20, 15]
    assert [w["spent"] for w in weeks[-2:]] == [150, 40]
    assert sum(w["earned"] for w in weeks) == 35


def test_warns_when_earning_runs_well_ahead_of_spending():
    coord, storage, kid, cinema, xbox = _system()
    for d in (0, 7, 14, 21):
        _earn(storage, kid, d, 100)
    _spend(storage, kid, xbox, 2)
    _spend(storage, kid, xbox, 9)
    _spend(storage, kid, cinema, 3)
    for d in (35, 42):
        _earn(storage, kid, d, 50)
    report = _report(coord)
    assert report["recent_earned"] == 400 and report["recent_spent"] == 280
    assert report["inflating"] is False  # 400 < 1.5 x 280
    assert report["candidates"] == []

    for d in (1, 8, 15):
        _earn(storage, kid, d, 100)
    report = _report(coord)
    assert report["recent_earned"] >= ECONOMY_RATIO * report["recent_spent"]
    assert report["inflating"] is True
    assert report["earned_growth_pct"] == round((700 - 100) * 100 / 100)
    # Most-claimed first.
    assert [c["name"] for c in report["candidates"]] == ["30 min Xbox", "Cinema trip"]
    assert report["candidates"][0]["claims"] == 2


def test_a_quiet_month_never_warns():
    coord, storage, kid, *_ = _system()
    _earn(storage, kid, 1, ECONOMY_MIN_EARNED - 1)
    assert _report(coord)["inflating"] is False


def test_adults_are_left_out():
    coord, storage, kid, *_ = _system()
    kid.is_adult = True
    storage.update_child(kid)
    _earn(storage, kid, 1, 500)
    report = _report(coord)
    assert report["recent_earned"] == 0 and report["inflating"] is False
