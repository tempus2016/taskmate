"""Boost windows (#1100): a timed multiplier on chosen chores the kids can see coming."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, patch

import pytest

from .test_completion_eligibility import _now, run
from .test_family_care import _at, _family, _fired

BOOSTS = "custom_components.taskmate.coord_boosts.dt_util"
CHORES = "custom_components.taskmate.coord_chores.dt_util"


def _clock(mod, when=None):
    import contextlib

    when = when or _now()
    stack = contextlib.ExitStack()
    for ctx in (_at(mod, when), patch(f"{BOOSTS}.now", return_value=when), patch(f"{CHORES}.now", return_value=when)):
        stack.enter_context(ctx)
    return stack


def _setup():
    coord, storage, mod, kid, chore = _family(requires_approval=False, daily_limit=5)
    coord._celebrate = AsyncMock()
    coord.badges = None
    with _clock(mod):
        other = run(coord.async_add_chore("Bins", points=4, requires_approval=False, schedule_mode="specific_days"))
        leo = run(coord.async_add_child("Leo"))
    other.daily_limit = 5
    storage.update_chore(other)
    return coord, storage, mod, kid, chore, other, leo


def _points(storage, kid):
    return storage.get_child(kid.id).points


class TestStart:
    def test_boosted_chore_pays_the_multiplier_for_the_window_only(self):
        coord, storage, mod, kid, chore, other, _leo = _setup()
        with _clock(mod):
            boost = run(coord.async_start_boost(multiplier=2, minutes=60, chore_ids=[chore.id]))
            assert boost["multiplier"] == 2.0 and boost["status"] == "active"
            comp = run(coord.async_complete_chore(chore.id, kid.id))
            assert comp.points_awarded == 10 and comp.submitted_points == 10
            # Not on the list: ordinary pay.
            comp2 = run(coord.async_complete_chore(other.id, kid.id))
            assert comp2.points_awarded == 4
        assert _points(storage, kid) == 14
        with _clock(mod, _now() + dt.timedelta(minutes=61)):
            comp3 = run(coord.async_complete_chore(chore.id, kid.id))
            assert comp3.points_awarded == 5
        (evt,) = _fired(coord, "taskmate_boost_started")
        assert evt["multiplier"] == 2.0 and evt["chore_ids"] == [chore.id] and evt["minutes"] == 60

    def test_all_chores_and_only_some_children(self):
        coord, storage, mod, kid, chore, other, leo = _setup()
        with _clock(mod):
            run(coord.async_start_boost(multiplier=1.5, minutes=30, child_ids=[leo.id]))
            assert run(coord.async_complete_chore(chore.id, kid.id)).points_awarded == 5
            assert run(coord.async_complete_chore(other.id, leo.id)).points_awarded == 6  # 4 × 1.5

    def test_overlapping_boosts_pay_the_best_one(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        with _clock(mod):
            run(coord.async_start_boost(multiplier=2, minutes=30))
            run(coord.async_start_boost(multiplier=3, minutes=10, chore_ids=[chore.id]))
            assert run(coord.async_complete_chore(chore.id, kid.id)).points_awarded == 15

    def test_notifies_the_children_it_covers(self):
        coord, storage, mod, kid, chore, _other, leo = _setup()
        coord.notifications.fire.reset_mock()
        with _clock(mod):
            run(
                coord.async_start_boost(
                    multiplier=2, minutes=45, chore_ids=[chore.id], child_ids=[leo.id], name="Guests at 6"
                )
            )
        call = coord.notifications.fire.call_args
        assert call.args[0] == "boost_started"
        ctx = call.args[1]
        assert (
            ctx["multiplier"] == "2"
            and ctx["minutes"] == 45
            and ctx["chores_text"] == "Tidy room"
            and ctx["name"] == "Guests at 6"
        )
        assert call.kwargs["only_recipients"] == {f"child:{leo.id}"}

    def test_no_push_when_asked_not_to(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        coord.notifications.fire.reset_mock()
        with _clock(mod):
            run(coord.async_start_boost(multiplier=2, minutes=45, notify=False))
        coord.notifications.fire.assert_not_called()

    def test_validation(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        with _clock(mod):
            with pytest.raises(ValueError, match="multiplier"):
                run(coord.async_start_boost(multiplier=1, minutes=30))
            with pytest.raises(ValueError, match="multiplier"):
                run(coord.async_start_boost(multiplier=9, minutes=30))
            with pytest.raises(ValueError, match="minutes"):
                run(coord.async_start_boost(multiplier=2, minutes=0))
            with pytest.raises(ValueError, match="[Cc]hore"):
                run(coord.async_start_boost(multiplier=2, minutes=30, chore_ids=["nope"]))
            with pytest.raises(ValueError, match="[Cc]hild"):
                run(coord.async_start_boost(multiplier=2, minutes=30, child_ids=["nope"]))
            with pytest.raises(ValueError, match="past"):
                run(coord.async_start_boost(multiplier=2, minutes=30, starts_at=_now() - dt.timedelta(hours=2)))


class TestLifecycle:
    def test_state_lists_active_and_upcoming_with_names(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        with _clock(mod):
            run(coord.async_start_boost(multiplier=2, minutes=30, chore_ids=[chore.id]))
            run(
                coord.async_start_boost(
                    multiplier=3, minutes=20, starts_at=_now() + dt.timedelta(hours=2), name="Tea time"
                )
            )
            state = coord.boosts_state()
        assert [b["status"] for b in state] == ["active", "upcoming"]
        assert state[0]["chore_ids"] == [chore.id] and state[0]["chore_names"] == ["Tidy room"]
        assert state[0]["child_ids"] == [] and state[0]["ends_at"] > state[0]["starts_at"]
        assert state[1]["name"] == "Tea time" and state[1]["multiplier"] == 3.0
        with _clock(mod, _now() + dt.timedelta(hours=5)):
            assert coord.boosts_state() == []

    def test_upcoming_boost_is_announced_when_it_begins(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        with _clock(mod):
            run(coord.async_start_boost(multiplier=2, minutes=20, starts_at=_now() + dt.timedelta(hours=1)))
        assert _fired(coord, "taskmate_boost_started") == []
        coord.notifications.fire.reset_mock()
        with _clock(mod, _now() + dt.timedelta(minutes=30)):
            assert run(coord.async_check_boosts()) == 0
            assert run(coord.async_complete_chore(chore.id, kid.id)).points_awarded == 5
        with _clock(mod, _now() + dt.timedelta(hours=1, minutes=1)):
            assert run(coord.async_check_boosts()) == 1
            assert run(coord.async_check_boosts()) == 0
            assert run(coord.async_complete_chore(chore.id, kid.id)).points_awarded == 10
        assert len(_fired(coord, "taskmate_boost_started")) == 1
        assert [c.args[0] for c in coord.notifications.fire.call_args_list].count("boost_started") == 1

    def test_ending_fires_once_on_its_own_and_early_by_hand(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        with _clock(mod):
            b1 = run(coord.async_start_boost(multiplier=2, minutes=10))
            b2 = run(coord.async_start_boost(multiplier=2, minutes=120, name="Long"))
            run(coord.async_end_boost(b2["id"]))
            with pytest.raises(ValueError):
                run(coord.async_end_boost(b2["id"]))
            with pytest.raises(ValueError):
                run(coord.async_end_boost("nope"))
            assert [b["id"] for b in coord.boosts_state()] == [b1["id"]]
        ended = _fired(coord, "taskmate_boost_ended")
        assert [(e["id"], e["ended_early"]) for e in ended] == [(b2["id"], True)]
        with _clock(mod, _now() + dt.timedelta(minutes=11)):
            assert run(coord.async_check_boosts()) == 1
            assert run(coord.async_check_boosts()) == 0
            assert coord.boosts_state() == []
        ended = _fired(coord, "taskmate_boost_ended")
        assert [(e["id"], e["ended_early"]) for e in ended] == [(b2["id"], True), (b1["id"], False)]

    def test_old_boosts_are_pruned(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        with _clock(mod):
            for i in range(25):
                run(coord.async_start_boost(multiplier=2, minutes=1, name=f"b{i}"))
        with _clock(mod, _now() + dt.timedelta(hours=1)):
            run(coord.async_check_boosts())
        assert len(storage.get_section("boosts", list)) == 20


class TestSpecialDays:
    """Saturday 2024-03-23 pays the weekend ×2. ``boost_stacking`` decides."""

    SAT = dt.datetime(2024, 3, 23, 12, 0, tzinfo=dt.UTC)

    def test_highest_wins_by_default(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        with _clock(mod, self.SAT):
            run(coord.async_start_boost(multiplier=3, minutes=30))
            comp = run(coord.async_complete_chore(chore.id, kid.id))
        # 5 × 3, the weekend ×2 dropped.
        assert comp.points_awarded == 15
        assert comp.boost_multiplier == 3.0 and comp.boost_stacked is False

    def test_highest_wins_keeps_the_weekend_when_it_is_bigger(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        with _clock(mod, self.SAT):
            run(coord.async_start_boost(multiplier=1.5, minutes=30))
            comp = run(coord.async_complete_chore(chore.id, kid.id))
        assert comp.points_awarded == 10
        assert comp.boost_multiplier == 0

    def test_stack_multiplies_both(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        storage.set_setting("boost_stacking", "stack")
        with _clock(mod, self.SAT):
            run(coord.async_start_boost(multiplier=2, minutes=30))
            comp = run(coord.async_complete_chore(chore.id, kid.id))
        assert comp.points_awarded == 20 and comp.boost_stacked is True

    def test_approval_later_pays_what_the_window_promised(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        chore.requires_approval = True
        storage.update_chore(chore)
        with _clock(mod, self.SAT):
            run(coord.async_start_boost(multiplier=3, minutes=30))
            comp = run(coord.async_complete_chore(chore.id, kid.id))
            assert comp.submitted_points == 15 and comp.points_awarded == 0
        with _clock(mod, self.SAT + dt.timedelta(hours=3)):
            run(coord.async_approve_chore(comp.id))
        stored = next(c for c in storage.get_completions() if c.id == comp.id)
        # No weekend double on top in highest-wins mode, and the window being
        # over by approval time changes nothing.
        assert stored.points_awarded == 15

    def test_old_completions_load_without_a_boost(self):
        from custom_components.taskmate.models import ChoreCompletion

        c = ChoreCompletion.from_dict({"chore_id": "x", "child_id": "y", "completed_at": _now().isoformat()})
        assert c.boost_multiplier == 0 and c.boost_stacked is False
        assert "boost_multiplier" not in c.to_dict()


class TestRules:
    def _rule(self, coord, **over):
        rule = {
            "name": "Saturday garden",
            "days": [5],
            "start": "09:00",
            "end": "11:00",
            "multiplier": 2,
            "enabled": True,
        }
        rule.update(over)
        return run(coord.async_save_boost_rule(rule))

    def test_a_rule_starts_and_ends_a_boost_on_its_days(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        sat9 = dt.datetime(2024, 3, 23, 9, 0, 30, tzinfo=dt.UTC)
        with _clock(mod, sat9):
            rule = self._rule(coord, chore_ids=[chore.id])
            assert run(coord.async_check_boosts()) >= 1
            (b,) = coord.boosts_state()
            assert b["rule_id"] == rule["id"] and b["status"] == "active" and b["name"] == "Saturday garden"
            assert b["ends_at"].startswith("2024-03-23T11:00")
            run(coord.async_check_boosts())
            assert len(coord.boosts_state()) == 1, "one boost per rule per day"
        with _clock(mod, dt.datetime(2024, 3, 23, 11, 1, tzinfo=dt.UTC)):
            run(coord.async_check_boosts())
            assert coord.boosts_state() == []
        # Not on a Sunday.
        with _clock(mod, dt.datetime(2024, 3, 24, 9, 30, tzinfo=dt.UTC)):
            run(coord.async_check_boosts())
            assert coord.boosts_state() == []

    def test_upcoming_rule_shows_ahead_of_time_and_disabled_rules_do_nothing(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        with _clock(mod, dt.datetime(2024, 3, 23, 7, 0, tzinfo=dt.UTC)):
            rule = self._rule(coord)
            (b,) = coord.boosts_state()
            assert b["status"] == "upcoming" and b["rule_id"] == rule["id"]
            run(coord.async_save_boost_rule({**rule, "enabled": False}))
            assert coord.boosts_state() == []

    def test_ending_a_rule_boost_early_holds_for_the_day(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        with _clock(mod, dt.datetime(2024, 3, 23, 9, 5, tzinfo=dt.UTC)):
            self._rule(coord)
            run(coord.async_check_boosts())
            (b,) = coord.boosts_state()
            run(coord.async_end_boost(b["id"]))
            run(coord.async_check_boosts())
            assert coord.boosts_state() == []

    def test_rule_validation_and_delete(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        with _clock(mod):
            with pytest.raises(ValueError, match="day"):
                self._rule(coord, days=[])
            with pytest.raises(ValueError, match="end"):
                self._rule(coord, start="11:00", end="09:00")
            with pytest.raises(ValueError, match="multiplier"):
                self._rule(coord, multiplier=7)
            with pytest.raises(ValueError, match="time"):
                self._rule(coord, start="9am")
            rule = self._rule(coord)
            assert [r["id"] for r in coord.boost_rules()] == [rule["id"]]
            run(coord.async_delete_boost_rule(rule["id"]))
            assert coord.boost_rules() == []
            with pytest.raises(ValueError):
                run(coord.async_delete_boost_rule(rule["id"]))


class TestWake:
    def _registry(self, entries):
        from types import SimpleNamespace

        reg = SimpleNamespace(entities={e.entity_id: e for e in entries})
        reg.async_get = lambda eid: reg.entities.get(eid)
        return reg

    def _fkb(self, entity_id, unique_id):
        from types import SimpleNamespace

        return SimpleNamespace(
            entity_id=entity_id, platform="fully_kiosk", unique_id=unique_id, domain=entity_id.split(".")[0]
        )

    def test_fully_kiosk_screen_is_turned_on_screensaver_off_and_browser_brought_forward(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        coord.hass.services.async_call = AsyncMock()
        coord.hass.services.has_service = lambda domain, service: True
        reg = self._registry(
            [
                self._fkb("switch.kitchen_screen", "abc123-screenOn"),
                self._fkb("switch.kitchen_screensaver", "abc123-screensaver"),
                self._fkb("button.kitchen_bring_to_foreground", "abc123-toForeground"),
                self._fkb("switch.hall_screen", "zzz-screenOn"),
            ]
        )
        storage.set_setting("boost_wake_screens", ["switch.kitchen_screen"])
        storage.set_setting("boost_wake_devices", ["mobile_app_wall_tablet"])
        with patch("custom_components.taskmate.coord_boosts.er.async_get", return_value=reg), _clock(mod):
            run(coord.async_start_boost(multiplier=2, minutes=30))
        calls = [(c.args[0], c.args[1], c.args[2]) for c in coord.hass.services.async_call.call_args_list]
        assert ("switch", "turn_on", {"entity_id": "switch.kitchen_screen"}) in calls
        assert ("switch", "turn_off", {"entity_id": "switch.kitchen_screensaver"}) in calls
        assert ("button", "press", {"entity_id": "button.kitchen_bring_to_foreground"}) in calls
        assert ("notify", "mobile_app_wall_tablet", {"message": "command_screen_on"}) in calls
        assert not any("hall" in str(c) for c in calls)

    def test_only_fully_kiosk_screens_and_companion_apps_are_ever_called(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        coord.hass.services.async_call = AsyncMock()
        coord.hass.services.has_service = lambda domain, service: True
        reg = self._registry([self._fkb("switch.kitchen_screensaver", "abc123-screensaver")])
        storage.set_setting("boost_wake_screens", ["switch.garage_door", "switch.kitchen_screensaver", "lock.front"])
        storage.set_setting("boost_wake_devices", ["persistent_notification", "mobile_app_x; rm"])
        with patch("custom_components.taskmate.coord_boosts.er.async_get", return_value=reg), _clock(mod):
            run(coord.async_start_boost(multiplier=2, minutes=30))
        coord.hass.services.async_call.assert_not_called()

    def test_a_scheduled_boost_wakes_when_it_begins_not_when_it_is_made(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        coord.hass.services.async_call = AsyncMock()
        coord.hass.services.has_service = lambda domain, service: True
        storage.set_setting("boost_wake_devices", ["mobile_app_wall_tablet"])
        with _clock(mod):
            run(coord.async_start_boost(multiplier=2, minutes=30, starts_at=_now() + dt.timedelta(hours=1)))
        coord.hass.services.async_call.assert_not_called()
        with _clock(mod, _now() + dt.timedelta(hours=1, seconds=5)):
            run(coord.async_check_boosts())
        coord.hass.services.async_call.assert_awaited()

    def test_a_wake_failure_never_stops_the_boost(self):
        coord, storage, mod, kid, chore, _other, _leo = _setup()
        coord.hass.services.async_call = AsyncMock(side_effect=RuntimeError("tablet offline"))
        coord.hass.services.has_service = lambda domain, service: True
        storage.set_setting("boost_wake_devices", ["mobile_app_wall_tablet"])
        with _clock(mod):
            b = run(coord.async_start_boost(multiplier=2, minutes=30))
            assert coord.boosts_state()[0]["id"] == b["id"]


def test_skipping_todays_recurring_boost_before_it_starts():
    coord, storage, mod, kid, chore, _other, _leo = _setup()
    with _clock(mod, dt.datetime(2024, 3, 23, 7, 0, tzinfo=dt.UTC)):
        run(
            coord.async_save_boost_rule({"name": "Sat", "days": [5], "start": "09:00", "end": "11:00", "multiplier": 2})
        )
        (row,) = coord.boosts_state()
        assert row["id"].startswith("rule:")
        run(coord.async_end_boost(row["id"]))
        assert coord.boosts_state() == []
    with _clock(mod, dt.datetime(2024, 3, 23, 9, 30, tzinfo=dt.UTC)):
        run(coord.async_check_boosts())
        assert coord.boosts_state() == []
        assert run(coord.async_complete_chore(chore.id, kid.id)).points_awarded == 10  # weekend ×2 only
    assert _fired(coord, "taskmate_boost_started") == []
    # Next Saturday it runs again.
    with _clock(mod, dt.datetime(2024, 3, 30, 9, 30, tzinfo=dt.UTC)):
        run(coord.async_check_boosts())
        assert [b["status"] for b in coord.boosts_state()] == ["active"]


def test_a_rule_saved_part_way_through_its_window_starts_for_the_rest_of_it():
    coord, storage, mod, kid, chore, _other, _leo = _setup()
    with _clock(mod, dt.datetime(2024, 3, 23, 9, 40, tzinfo=dt.UTC)):
        run(
            coord.async_save_boost_rule({"name": "Sat", "days": [5], "start": "09:00", "end": "11:00", "multiplier": 2})
        )
        assert run(coord.async_check_boosts()) >= 1
        (b,) = coord.boosts_state()
        assert not b["id"].startswith("rule:") and b["status"] == "active"
    assert len(_fired(coord, "taskmate_boost_started")) == 1
