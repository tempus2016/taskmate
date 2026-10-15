"""Raffles: tickets bought with points, a weighted draw, refunds when called off."""

from __future__ import annotations

import datetime as dt
import random
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .test_completion_eligibility import _make_system, _now, run

RAFFLES = "custom_components.taskmate.coord_raffles.dt_util.now"


def _setup(points=100):
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    coord.hass.bus = MagicMock()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        a = run(coord.async_add_child("Malia"))
        b = run(coord.async_add_child("Vaiha"))
    for kid in (a, b):
        kid = storage.get_child(kid.id)
        kid.points = points
        storage.update_child(kid)
    return coord, storage, a, b


def _raffle(coord, **over):
    fields = {
        "name": "Saturday raffle",
        "prize": "Cinema trip",
        "ticket_cost": 10,
        "draw_at": (_now() + dt.timedelta(days=2)).isoformat(),
        **over,
    }
    with patch(RAFFLES, return_value=_now()):
        return run(coord.async_create_raffle(**fields))


class TestSetUp:
    def test_create_needs_a_future_draw(self):
        coord, _s, _a, _b = _setup()
        with patch(RAFFLES, return_value=_now()), pytest.raises(ValueError, match="future"):
            run(coord.async_create_raffle(name="x", ticket_cost=5, draw_at=_now().isoformat()))

    def test_price_is_fixed_once_tickets_are_sold(self):
        coord, _s, a, _b = _setup()
        raffle = _raffle(coord)
        with patch(RAFFLES, return_value=_now()):
            run(coord.async_buy_raffle_tickets(raffle["id"], a.id, 1))
            with pytest.raises(ValueError, match="price"):
                run(coord.async_update_raffle(raffle["id"], ticket_cost=20))
            run(coord.async_update_raffle(raffle["id"], prize="Bowling"))
        assert coord.get_raffle(raffle["id"])["prize"] == "Bowling"


class TestTickets:
    def test_buying_spends_points(self):
        coord, storage, a, _b = _setup()
        raffle = _raffle(coord)
        with patch(RAFFLES, return_value=_now()):
            assert run(coord.async_buy_raffle_tickets(raffle["id"], a.id, 3)) == 3
        assert storage.get_child(a.id).points == 70
        assert coord.raffles_state()[0]["tickets"] == {a.id: 3}

    def test_cap_and_balance_are_enforced(self):
        coord, _s, a, _b = _setup(points=25)
        raffle = _raffle(coord, max_tickets=2)
        with patch(RAFFLES, return_value=_now()):
            with pytest.raises(ValueError, match="at most 2"):
                run(coord.async_buy_raffle_tickets(raffle["id"], a.id, 3))
            run(coord.async_buy_raffle_tickets(raffle["id"], a.id, 2))
        coord2, _s2, a2, _b2 = _setup(points=15)
        raffle2 = _raffle(coord2)
        with patch(RAFFLES, return_value=_now()), pytest.raises(ValueError, match="Not enough"):
            run(coord2.async_buy_raffle_tickets(raffle2["id"], a2.id, 2))

    def test_only_children_it_is_open_to(self):
        coord, _s, a, b = _setup()
        raffle = _raffle(coord, assigned_to=[a.id])
        with patch(RAFFLES, return_value=_now()), pytest.raises(ValueError, match="isn't open"):
            run(coord.async_buy_raffle_tickets(raffle["id"], b.id, 1))

    def test_no_tickets_after_the_draw_time(self):
        coord, _s, a, _b = _setup()
        raffle = _raffle(coord)
        later = _now() + dt.timedelta(days=3)
        with patch(RAFFLES, return_value=later), pytest.raises(ValueError):
            run(coord.async_buy_raffle_tickets(raffle["id"], a.id, 1))


class TestDraw:
    def test_draw_is_weighted_by_tickets(self):
        coord, _s, a, b = _setup()
        raffle = _raffle(coord)
        with patch(RAFFLES, return_value=_now()):
            run(coord.async_buy_raffle_tickets(raffle["id"], a.id, 1))
            run(coord.async_buy_raffle_tickets(raffle["id"], b.id, 9))
        wins = {a.id: 0, b.id: 0}
        rng = random.Random(7)
        for _ in range(200):
            r = coord.get_raffle(raffle["id"])
            r["status"] = "open"
            with patch(RAFFLES, return_value=_now()):
                wins[run(coord.async_draw_raffle(raffle["id"], rng=rng))] += 1
        assert wins[b.id] > wins[a.id] * 4

    def test_draw_records_the_winner_and_announces_it(self):
        coord, _s, a, _b = _setup()
        raffle = _raffle(coord)
        with patch(RAFFLES, return_value=_now()):
            run(coord.async_buy_raffle_tickets(raffle["id"], a.id, 2))
            winner = run(coord.async_draw_raffle(raffle["id"]))
        assert winner == a.id
        assert coord.get_raffle(raffle["id"])["status"] == "drawn"
        assert coord.notifications.fire.call_args.args[0] == "raffle_drawn"
        events = [c.args[0] for c in coord.hass.bus.async_fire.call_args_list]
        assert "taskmate_raffle_won" in events

    def test_nobody_entered(self):
        coord, _s, _a, _b = _setup()
        raffle = _raffle(coord)
        with patch(RAFFLES, return_value=_now()):
            assert run(coord.async_draw_raffle(raffle["id"])) == ""
        assert coord.get_raffle(raffle["id"])["status"] == "drawn"

    def test_due_raffles_draw_themselves(self):
        coord, _s, a, _b = _setup()
        raffle = _raffle(coord)
        with patch(RAFFLES, return_value=_now()):
            run(coord.async_buy_raffle_tickets(raffle["id"], a.id, 1))
            assert run(coord.async_draw_due_raffles()) == 0
        with patch(RAFFLES, return_value=_now() + dt.timedelta(days=3)):
            assert run(coord.async_draw_due_raffles()) == 1
        assert coord.get_raffle(raffle["id"])["winner_id"] == a.id

    def test_drawn_raffles_leave_the_cards_after_a_day(self):
        coord, _s, _a, _b = _setup()
        raffle = _raffle(coord)
        with patch(RAFFLES, return_value=_now()):
            run(coord.async_draw_raffle(raffle["id"]))
            assert len(coord.raffles_state()) == 1
        with patch(RAFFLES, return_value=_now() + dt.timedelta(days=2)):
            assert coord.raffles_state() == []


class TestCancel:
    def test_calling_it_off_refunds_every_ticket(self):
        coord, storage, a, b = _setup()
        raffle = _raffle(coord)
        with patch(RAFFLES, return_value=_now()):
            run(coord.async_buy_raffle_tickets(raffle["id"], a.id, 2))
            run(coord.async_buy_raffle_tickets(raffle["id"], b.id, 1))
            run(coord.async_cancel_raffle(raffle["id"]))
        assert storage.get_child(a.id).points == 100
        assert storage.get_child(b.id).points == 100
        assert coord.get_raffle(raffle["id"])["status"] == "cancelled"

    def test_removing_an_open_raffle_refunds_first(self):
        coord, storage, a, _b = _setup()
        raffle = _raffle(coord)
        with patch(RAFFLES, return_value=_now()):
            run(coord.async_buy_raffle_tickets(raffle["id"], a.id, 4))
            run(coord.async_remove_raffle(raffle["id"]))
        assert storage.get_child(a.id).points == 100
        assert coord.get_raffle(raffle["id"]) is None


def test_trimming_old_raffles_never_drops_an_open_one():
    coord, storage, a, _b = _setup()
    first = _raffle(coord, name="Long-running")
    with patch(RAFFLES, return_value=_now()):
        run(coord.async_buy_raffle_tickets(first["id"], a.id, 2))
    with patch("custom_components.taskmate.coord_raffles.RAFFLES_KEEP", 2):
        _raffle(coord, name="Second")
        _raffle(coord, name="Third")
    assert coord.get_raffle(first["id"]) is not None
    assert coord.get_raffle(first["id"])["tickets"] == {a.id: 2}


def test_trim_finished_drops_only_closed_records_oldest_first():
    from custom_components.taskmate.coord_raffles import _trim_finished

    records = [
        {"id": 1, "status": "open"},
        {"id": 2, "status": "drawn"},
        {"id": 3, "status": "drawn"},
        {"id": 4, "status": "open"},
    ]
    _trim_finished(records, 3, keep=("open",))
    assert [r["id"] for r in records] == [1, 3, 4]
