"""Tests for birthday mode (#924).

A child may carry an optional ``birthday`` ("YYYY-MM-DD" or "MM-DD"). On that
day chore points are multiplied (on top of the weekend bonus), non-mandatory
chores can be given the day off without costing the streak, a built-in
Birthday badge is awarded and a celebration fires once. 29 February birthdays
are celebrated on 28 February in non-leap years.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import pathlib
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.coord_badges import (
    BUILTIN_CATALOGUE,
    TRIGGER_METRICS,
    resolve_metric,
)
from custom_components.taskmate.coord_birthdays import (
    birthday_in_year,
    is_birthday_on,
    normalize_birthday,
    parse_birthday,
)
from custom_components.taskmate.coord_notifications import (
    NOTIFICATION_TYPES_BY_ID,
    NotificationCoordinator,
)
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, NotificationConfig, NotificationRoute

UTC = dt.timezone.utc
WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"


def _at(y: int, m: int, d: int) -> dt.datetime:
    return dt.datetime(y, m, d, 12, 0, 0, tzinfo=UTC)


def _make_coord(settings=None, children=None, chores=None) -> TaskMateCoordinator:
    coord = object.__new__(TaskMateCoordinator)
    _settings = dict(settings or {})
    _children = children or []
    by_id = {c.id: c for c in _children}
    coord.hass = MagicMock()
    coord.hass.states.get = MagicMock(return_value=None)
    coord.data = {}
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": _settings.get(k, d))
    storage.set_setting = MagicMock(side_effect=lambda k, v: _settings.__setitem__(k, v))
    storage.get_children = MagicMock(return_value=_children)
    storage.get_child = MagicMock(side_effect=lambda cid: by_id.get(cid))
    storage.get_chores = MagicMock(return_value=chores or [])
    storage.get_completions = MagicMock(return_value=[])
    storage.update_child = MagicMock()
    storage.add_points_transaction = MagicMock()
    storage.append_career_score_snapshot = MagicMock()
    storage.async_save = AsyncMock()
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    coord.notifications = None
    coord._settings = _settings
    return coord


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _now(value: dt.datetime):
    import custom_components.taskmate.coordinator as _mod

    return patch.object(_mod.dt_util, "now", return_value=value)


# ── Parsing ──────────────────────────────────────────────────────────────────


class TestParsing:
    def test_full_date(self):
        assert parse_birthday("2016-05-12") == (2016, 5, 12)

    def test_year_optional(self):
        assert parse_birthday("05-12") == (None, 5, 12)
        assert parse_birthday("--05-12") == (None, 5, 12)

    def test_leap_day_without_year_is_valid(self):
        assert parse_birthday("02-29") == (None, 2, 29)

    @pytest.mark.parametrize("bad", ["", "2016-13-01", "2015-02-29", "12/05/2016", "5-12", "02-30", "abc"])
    def test_rejects_invalid(self, bad):
        with pytest.raises(ValueError):
            parse_birthday(bad)

    def test_normalize_clears_and_canonicalises(self):
        assert normalize_birthday("") == ""
        assert normalize_birthday("  ") == ""
        assert normalize_birthday("--05-12") == "05-12"
        with _now(_at(2026, 9, 27)):
            assert normalize_birthday("2016-05-12") == "2016-05-12"

    def test_normalize_rejects_future_birth_year(self):
        with _now(_at(2026, 9, 27)), pytest.raises(ValueError):
            normalize_birthday("2030-01-01")


class TestLeapDay:
    def test_feb_29_falls_back_to_feb_28_in_non_leap_years(self):
        assert birthday_in_year("2016-02-29", 2027) == date(2027, 2, 28)
        assert is_birthday_on("02-29", date(2027, 2, 28)) is True
        assert is_birthday_on("02-29", date(2027, 3, 1)) is False

    def test_feb_29_celebrated_on_the_day_in_leap_years(self):
        assert birthday_in_year("2016-02-29", 2028) == date(2028, 2, 29)
        assert is_birthday_on("2016-02-29", date(2028, 2, 29)) is True
        assert is_birthday_on("2016-02-29", date(2028, 2, 28)) is False

    def test_unset_or_garbage_is_never_a_birthday(self):
        assert is_birthday_on("", date(2026, 1, 1)) is False
        assert is_birthday_on("nope", date(2026, 1, 1)) is False
        assert is_birthday_on(None, date(2026, 1, 1)) is False


class TestChildHelpers:
    def test_is_birthday_and_age(self):
        child = Child(name="Mia", birthday="2016-09-27")
        coord = _make_coord(children=[child])
        with _now(_at(2026, 9, 27)):
            assert coord.is_birthday(child) is True
            assert coord.birthday_age(child) == 10
        with _now(_at(2026, 9, 28)):
            assert coord.is_birthday(child) is False

    def test_age_omitted_without_year(self):
        child = Child(name="Mia", birthday="09-27")
        coord = _make_coord(children=[child])
        with _now(_at(2026, 9, 27)):
            assert coord.birthday_age(child) is None
            assert coord.birthday_summary(child) == {"multiplier": 2.0}

    def test_summary_carries_age_and_day_off(self):
        child = Child(name="Mia", birthday="2016-09-27")
        coord = _make_coord({"birthday_chores_off": True, "birthday_points_multiplier": 3.0}, [child])
        with _now(_at(2026, 9, 27)):
            assert coord.birthday_summary(child) == {"multiplier": 3.0, "age": 10, "chores_off": True}
        with _now(_at(2026, 9, 26)):
            assert coord.birthday_summary(child) is None

    def test_multiplier_below_one_is_clamped(self):
        coord = _make_coord({"birthday_points_multiplier": 0.5})
        assert coord.birthday_multiplier() == 1.0
        coord = _make_coord({"birthday_points_multiplier": "garbage"})
        assert coord.birthday_multiplier() == 2.0


# ── Points ───────────────────────────────────────────────────────────────────


class TestBirthdayMultiplier:
    def _award(self, coord, child, points, when):
        with _now(when):
            return run(coord._award_points(child, points, completion_date=when.date()))

    def test_doubles_points_on_the_birthday(self):
        child = Child(name="Mia", birthday="2016-09-23")  # a Wednesday in 2026
        coord = _make_coord({"weekend_multiplier": "1.0"}, [child])
        total = self._award(coord, child, 10, _at(2026, 9, 23))
        assert total == 20
        assert child.points == 20
        assert child.total_points_earned == 20

    def test_no_bonus_on_other_days(self):
        child = Child(name="Mia", birthday="2016-09-23")
        coord = _make_coord({"weekend_multiplier": "1.0"}, [child])
        assert self._award(coord, child, 10, _at(2026, 9, 24)) == 10

    def test_stacks_on_top_of_the_weekend_bonus(self):
        child = Child(name="Mia", birthday="2016-09-26")  # a Saturday in 2026
        coord = _make_coord({"weekend_multiplier": "2.0", "birthday_points_multiplier": 2.0}, [child])
        # 10 base -> 20 with the weekend -> 40 on the birthday.
        assert self._award(coord, child, 10, _at(2026, 9, 26)) == 40

    def test_multiplier_one_is_off(self):
        child = Child(name="Mia", birthday="2016-09-23")
        coord = _make_coord({"weekend_multiplier": "1.0", "birthday_points_multiplier": 1.0}, [child])
        assert self._award(coord, child, 10, _at(2026, 9, 23)) == 10

    def test_uses_the_completion_date_not_the_approval_date(self):
        # Completed on the birthday, approved the day after: still doubled.
        child = Child(name="Mia", birthday="2016-09-23")
        coord = _make_coord({"weekend_multiplier": "1.0"}, [child])
        with _now(_at(2026, 9, 24)):
            total = run(coord._award_points(child, 10, completion_date=date(2026, 9, 23)))
        assert total == 20


# ── Day off ──────────────────────────────────────────────────────────────────


class TestDayOff:
    def test_non_mandatory_chores_hidden_mandatory_kept(self):
        child = Child(name="Mia", birthday="2016-09-23")
        coord = _make_coord({"birthday_chores_off": True}, [child])
        optional = Chore(name="Tidy room", schedule_mode="specific_days", due_days=[])
        mandatory = Chore(name="Brush teeth", schedule_mode="specific_days", due_days=[], mandatory=True)
        with _now(_at(2026, 9, 23)):
            assert coord.is_chore_available_for_child(optional, child.id) is False
            assert coord.is_chore_available_for_child(mandatory, child.id) is True
        with _now(_at(2026, 9, 24)):
            assert coord.is_chore_available_for_child(optional, child.id) is True

    def test_chores_stay_when_setting_off(self):
        child = Child(name="Mia", birthday="2016-09-23")
        coord = _make_coord({}, [child])
        optional = Chore(name="Tidy room", schedule_mode="specific_days", due_days=[])
        with _now(_at(2026, 9, 23)):
            assert coord.is_chore_available_for_child(optional, child.id) is True

    def test_only_mandatory_chores_are_due(self):
        child = Child(name="Mia", birthday="2016-09-23")
        optional = Chore(name="Tidy room", schedule_mode="specific_days", due_days=[])
        mandatory = Chore(name="Brush teeth", schedule_mode="specific_days", due_days=[], mandatory=True)
        coord = _make_coord({"birthday_chores_off": True}, [child], [optional, mandatory])
        coord._is_chore_scheduled_for_date = MagicMock(return_value=True)
        due = coord._due_chore_ids_for_child(child.id, date(2026, 9, 23), include_rotation=False)
        assert due == {mandatory.id}
        due = coord._due_chore_ids_for_child(child.id, date(2026, 9, 24), include_rotation=False)
        assert due == {optional.id, mandatory.id}


class TestStreakProtection:
    def test_birthday_day_off_does_not_break_the_gap(self):
        child = Child(name="Mia", birthday="2016-09-23")
        coord = _make_coord({"birthday_chores_off": True}, [child])
        # Last completion the 22nd, today the 24th: only the birthday was missed.
        assert coord._streak_breaks_after_gap("2026-09-22", date(2026, 9, 24), child) is False

    def test_birthday_without_day_off_still_breaks(self):
        child = Child(name="Mia", birthday="2016-09-23")
        coord = _make_coord({}, [child])
        assert coord._streak_breaks_after_gap("2026-09-22", date(2026, 9, 24), child) is True

    def test_midnight_check_keeps_the_streak(self):
        child = Child(name="Mia", birthday="2016-09-23", current_streak=5, last_completion_date="2026-09-22")
        coord = _make_coord({"birthday_chores_off": True, "streak_reset_mode": "reset"}, [child])
        with _now(dt.datetime(2026, 9, 24, 0, 0, 5, tzinfo=UTC)):
            run(coord._async_check_streaks())
        assert child.current_streak == 5
        assert child.streak_paused is False

    def test_next_completion_continues_the_streak(self):
        child = Child(name="Mia", birthday="2016-09-23", current_streak=5, last_completion_date="2026-09-22")
        coord = _make_coord(
            {"birthday_chores_off": True, "streak_reset_mode": "reset", "streak_milestones_enabled": "false"},
            [child],
        )
        with _now(_at(2026, 9, 24)):
            run(coord._award_points(child, 10))
        assert child.current_streak == 6

    def test_a_real_missed_day_next_to_the_birthday_still_resets(self):
        child = Child(name="Mia", birthday="2016-09-23", current_streak=5, last_completion_date="2026-09-21")
        coord = _make_coord(
            {"birthday_chores_off": True, "streak_reset_mode": "reset", "streak_milestones_enabled": "false"},
            [child],
        )
        with _now(_at(2026, 9, 24)):
            run(coord._award_points(child, 10))
        assert child.current_streak == 1

    def test_birthday_day_off_never_spends_a_streak_freeze(self):
        child = Child(name="Mia", birthday="2016-09-23", current_streak=5, last_completion_date="2026-09-22")
        child.streak_freezes = 1
        coord = _make_coord({"birthday_chores_off": True}, [child])
        assert coord._unprotected_missed_days("2026-09-22", date(2026, 9, 24), child) == []

    def test_gap_of_a_frozen_day_and_the_birthday_is_bridged(self):
        # 22nd done, 23rd birthday off, 24th covered by a freeze, completing on the 25th.
        child = Child(name="Mia", birthday="2016-09-23", current_streak=5, last_completion_date="2026-09-22")
        child.streak_freeze_dates = ["2026-09-24"]
        coord = _make_coord(
            {"birthday_chores_off": True, "streak_reset_mode": "reset", "streak_milestones_enabled": "false"},
            [child],
        )
        with _now(_at(2026, 9, 25)):
            run(coord._award_points(child, 10))
        assert child.current_streak == 6


# ── Badge + celebration ──────────────────────────────────────────────────────


class TestBirthdayBadge:
    def test_builtin_badge_in_catalogue(self):
        badge = next(b for b in BUILTIN_CATALOGUE if b.id == "builtin.birthday")
        assert badge.criteria[0].metric == "birthday"
        assert TRIGGER_METRICS["birthday"] == {"birthday"}

    def test_metric_true_only_on_the_day(self):
        child = Child(name="Mia", birthday="2016-09-23")
        with _now(_at(2026, 9, 23)):
            assert resolve_metric("birthday", child, MagicMock()) == 1
        with _now(_at(2026, 9, 24)):
            assert resolve_metric("birthday", child, MagicMock()) == 0


class TestCheckBirthdays:
    def _coord(self, child):
        coord = _make_coord({}, [child])
        coord.badges = MagicMock()
        coord.badges.evaluate_for_child = AsyncMock()
        coord._celebrate = AsyncMock()
        return coord

    def test_celebrates_once_per_day(self):
        child = Child(name="Mia", birthday="2016-09-23")
        coord = self._coord(child)
        with _now(_at(2026, 9, 23)):
            assert run(coord.async_check_birthdays()) == [child.id]
            assert run(coord.async_check_birthdays()) == []
        coord.badges.evaluate_for_child.assert_awaited_once_with(child.id, "birthday")
        coord._celebrate.assert_awaited_once()
        args, kwargs = coord._celebrate.call_args
        assert args[1] == "birthday"
        assert kwargs["tier"] == 3
        assert kwargs["extra"] == {"multiplier": 2.0, "age": 10}

    def test_celebrates_again_next_year(self):
        child = Child(name="Mia", birthday="09-23")
        coord = self._coord(child)
        with _now(_at(2026, 9, 23)):
            run(coord.async_check_birthdays())
        with _now(_at(2027, 9, 23)):
            assert run(coord.async_check_birthdays()) == [child.id]

    def test_nothing_on_other_days(self):
        child = Child(name="Mia", birthday="2016-09-23")
        coord = self._coord(child)
        with _now(_at(2026, 9, 22)):
            assert run(coord.async_check_birthdays()) == []
        coord._celebrate.assert_not_awaited()
        coord.storage.async_save.assert_not_awaited()


# ── Model / sensor / websocket plumbing ──────────────────────────────────────


class TestPlumbing:
    def test_model_round_trip_and_old_data_default(self):
        child = Child(name="Mia", birthday="2016-09-23")
        assert Child.from_dict(child.to_dict()).birthday == "2016-09-23"
        assert Child.from_dict({"name": "Old"}).birthday == ""

    def test_child_summary_only_carries_birthday_on_the_day(self):
        child = Child(name="Mia", id="c1", birthday="2016-09-23")
        coord = _make_coord({}, [child])
        coord.level_info = MagicMock(return_value={"level": 1, "progress": 0, "target": 100})
        coord.roulette_enabled = MagicMock(return_value=False)
        coord.quest_progress_for_child = MagicMock(return_value=[])
        coord.challenge_progress_for_child = MagicMock(return_value=[])
        coord.avatar_options_for_child = MagicMock(return_value=[])
        coord._is_child_on_vacation = MagicMock(return_value=False)
        common = {
            "children": [child],
            "chores": [],
            "pending_points_by_child": {},
            "committed_points_by_child": {},
            "total_allocated_by_child": {},
            "season_points": {},
        }
        with _now(_at(2026, 9, 23)):
            summary = sensor_module._build_children_summary(coord, common)
        assert summary[0]["birthday"] == {"multiplier": 2.0, "age": 10}
        with _now(_at(2026, 9, 24)):
            summary = sensor_module._build_children_summary(coord, common)
        assert "birthday" not in summary[0]

    def test_settings_schema_accepts_birthday_keys(self):
        import voluptuous as vol

        from custom_components.taskmate.websocket import (
            _SUBKEY_SETTINGS,
            _UPDATE_SETTINGS_SCHEMA,
            WS_UPDATE_SETTINGS,
        )

        schema = vol.Schema(_UPDATE_SETTINGS_SCHEMA, extra=vol.ALLOW_EXTRA)
        schema({"type": WS_UPDATE_SETTINGS, "id": 1, "birthday_points_multiplier": 2.5, "birthday_chores_off": True})
        with pytest.raises(vol.Invalid):
            schema({"type": WS_UPDATE_SETTINGS, "id": 1, "birthday_points_multiplier": 0.5})
        assert {"birthday_points_multiplier", "birthday_chores_off"} <= _SUBKEY_SETTINGS


# ── Notification ─────────────────────────────────────────────────────────────


class TestBirthdayNotification:
    def _notif(self, child, coord):
        storage = MagicMock()
        storage.get_child = MagicMock(side_effect=lambda cid: child if cid == child.id else None)
        n = NotificationCoordinator(MagicMock(), storage)
        n.coordinator = coord
        n.fire = AsyncMock()
        return n

    def test_registered_as_child_time_gated_type(self):
        meta = NOTIFICATION_TYPES_BY_ID["birthday"]
        assert meta.audience == "child"
        assert meta.time_gated and meta.per_recipient_time
        assert meta.default_enabled is False

    def test_fires_only_on_the_birthday_with_the_multiplier(self):
        child = Child(name="Mia", birthday="2016-09-23")
        coord = _make_coord({"birthday_points_multiplier": 2.5}, [child])
        n = self._notif(child, coord)
        cb = n._make_birthday_callback(child.id)
        with _now(_at(2026, 9, 22)):
            run(cb(None))
        n.fire.assert_not_awaited()
        with _now(_at(2026, 9, 23)):
            run(cb(None))
        n.fire.assert_awaited_once()
        args, kwargs = n.fire.call_args
        assert args[0] == "birthday"
        assert args[1]["multiplier"] == "2.5"
        assert kwargs["only_recipients"] == {f"child:{child.id}"}

    def test_scheduled_at_eight_by_default(self):
        child = Child(name="Mia", birthday="2016-09-23")
        storage = MagicMock()
        cfgs = {
            "birthday": NotificationConfig(
                type_id="birthday",
                master_enabled=True,
                routes={f"child:{child.id}": NotificationRoute(enabled=True)},
            )
        }
        storage.get_notification_config = MagicMock(
            side_effect=lambda tid: cfgs.get(tid, NotificationConfig(type_id=tid))
        )
        storage.get_custom_notifications = MagicMock(return_value=[])
        n = NotificationCoordinator(MagicMock(), storage)
        with patch("custom_components.taskmate.coord_notifications.async_track_time_change") as track:
            track.return_value = lambda: None
            run(n.async_setup_schedules())
        assert [c.kwargs for c in track.call_args_list] == [{"hour": 8, "minute": 0, "second": 0}]

    def test_streak_at_risk_skips_a_birthday_day_off(self):
        child = Child(name="Mia", birthday="2016-09-23", current_streak=5, last_completion_date="2026-09-22")
        coord = _make_coord({"birthday_chores_off": True}, [child])
        n = self._notif(child, coord)
        n.storage.get_children = MagicMock(return_value=[child])
        with _now(_at(2026, 9, 23)):
            run(n._streak_at_risk_callback(None))
        n.fire.assert_not_awaited()


# ── Cards: both render paths ─────────────────────────────────────────────────


class TestCardsRenderOnEveryDesign:
    """The banner must be wired into BOTH render paths of each card — the
    classic branch alone leaves it invisible on every other design."""

    def _regions(self, source: str, designed_start: str, designed_end: str):
        classic = source[source.index("  render() {") : source.index(designed_start)]
        start = source.index(designed_start)
        designed = source[start : source.index(designed_end, start)]
        return classic, designed

    def test_child_card(self):
        src = (WWW / "taskmate-child-card.js").read_text(encoding="utf-8")
        classic, designed = self._regions(src, "_renderDesigned(design) {", "\n  _designHeaderFull(")
        assert "this._renderBirthdayBanner(child, false)" in classic
        assert "this._renderBirthdayBanner(child, true)" in designed
        # Confetti comes from updated(), which runs for every design.
        assert "this._maybeBirthdayConfetti(attrs)" in src

    def test_points_display_card(self):
        src = (WWW / "taskmate-points-display-card.js").read_text(encoding="utf-8")
        classic, designed = self._regions(src, "_renderDesigned(design) {", "\n  _designPlayroom(")
        assert "this._renderBirthdayBanners(false)" in classic
        assert "this._renderBirthdayBanners(true)" in designed
        assert "this._renderConfetti()" in classic and "this._renderConfetti()" in designed
