"""Two-way calendar (#977): add, move and remove chores from the HA calendar.

Covers the per-occurrence ``moved_occurrences`` map and every due-date path
that must honour it (calendar entity, ICS feed, availability / cards via the
chores sensor, reminders' due list, streaks, mandatory misses, reports), the
calendar entity's create/update/delete, the parent/admin gate on both doors
(websocket calendar panel and calendar.* services), and an end-to-end run
through a replica of Home Assistant's ``calendar/event/*`` websocket handlers.
"""

from __future__ import annotations

import asyncio
import contextvars
import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate import ics
from custom_components.taskmate.calendar import (
    TaskMateCalendar,
    _occurrence_uid,
    _parse_occurrence_uid,
)
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, clean_moved_occurrences
from custom_components.taskmate.sensor import _build_chores_list
from custom_components.taskmate.storage import TaskMateStorage

from .conftest import (
    FakeServiceValidationError,
    FakeUnauthorized,
    _ha_websocket_api_connection,
    dt_util_mock,
)

UTC = dt.timezone.utc
current_connection = _ha_websocket_api_connection.current_connection

# 2026-06-22 is a Monday.
MON = dt.date(2026, 6, 22)
TUE = dt.date(2026, 6, 23)
WED = dt.date(2026, 6, 24)
THU = dt.date(2026, 6, 25)
NEXT_MON = dt.date(2026, 6, 29)

ADMIN = "user-admin"
PARENT = "user-parent"
KID = "user-kid"


def _at(day: dt.date, hour: int = 9) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(hour, 0), tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clock():
    saved = dt_util_mock._now
    dt_util_mock._now = _at(MON)
    yield
    dt_util_mock._now = saved


async def _coord(hass, chores=(), children=None):
    storage = TaskMateStorage(hass, "cal977")
    await storage.async_load()
    kids = children or [Child(name="Alex", id="alex"), Child(name="Sam", id="sam")]
    for kid in kids:
        storage.add_child(kid)
    for chore in chores:
        storage.add_chore(chore)
    storage.set_parent_user_ids([PARENT])
    coord = object.__new__(TaskMateCoordinator)
    coord.hass = hass
    coord.storage = storage
    coord.data = {}
    users = {
        ADMIN: SimpleNamespace(id=ADMIN, name="Admin", is_admin=True),
        PARENT: SimpleNamespace(id=PARENT, name="Parent", is_admin=False),
        KID: SimpleNamespace(id=KID, name="Kid", is_admin=False),
    }
    hass.auth = MagicMock()
    hass.auth.async_get_user = AsyncMock(side_effect=lambda uid: users.get(uid))
    return coord


def _cal(coord, child_id="alex") -> TaskMateCalendar:
    cal = object.__new__(TaskMateCalendar)
    cal.coordinator = coord
    cal.hass = coord.hass
    cal._child_id = child_id
    cal._entry = MagicMock()
    return cal


def _chore_days(cal, start, end, name):
    child = cal._child
    return sorted(
        (e.start if not isinstance(e.start, dt.datetime) else e.start.date())
        for e in cal._build_events(child, start, end)
        if e.summary == name
    )


def _event(cal, day, name):
    return next(e for e in cal._build_events(cal._child, day, day) if e.summary == name)


# ── Model ────────────────────────────────────────────────────────────────


class TestModel:
    def test_old_data_defaults_to_empty(self):
        assert Chore.from_dict({"name": "Old"}).moved_occurrences == {}

    def test_round_trip(self):
        chore = Chore(name="Bins", moved_occurrences={"2026-06-22": "2026-06-24", "2026-06-29": ""})
        again = Chore.from_dict(chore.to_dict())
        assert again.moved_occurrences == {"2026-06-22": "2026-06-24", "2026-06-29": ""}

    def test_junk_is_dropped_not_raised(self):
        raw = {"2026-06-22": "2026-06-24", "garbage": "2026-06-25", "2026-06-23": "nope", "2026-06-26": None}
        assert clean_moved_occurrences(raw) == {"2026-06-22": "2026-06-24", "2026-06-26": ""}
        assert clean_moved_occurrences(["not", "a", "dict"]) == {}

    async def test_clone_starts_without_moves(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], moved_occurrences={"2026-06-22": ""})
        coord = await _coord(hass, [chore])
        clone = await coord.async_clone_chore(chore.id)
        assert clone.moved_occurrences == {}


# ── Scheduling core ──────────────────────────────────────────────────────


class TestScheduling:
    async def test_override_moves_and_removes(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], moved_occurrences={"2026-06-22": "2026-06-24"})
        coord = await _coord(hass, [chore])
        assert coord._is_chore_scheduled_for_date(chore, MON) is False
        assert coord._is_chore_scheduled_for_date(chore, WED) is True
        assert coord._is_chore_scheduled_for_date(chore, NEXT_MON) is True  # the series carries on
        chore.moved_occurrences = {"2026-06-22": ""}
        assert coord._is_chore_scheduled_for_date(chore, MON) is False
        assert coord._is_chore_scheduled_for_date(chore, WED) is False

    async def test_moved_onto_day_wins_over_moved_away(self, hass):
        # Mon -> Wed and Wed -> Fri: Wednesday still has Monday's occurrence.
        chore = Chore(
            name="Daily", due_days=[], moved_occurrences={"2026-06-22": "2026-06-24", "2026-06-24": "2026-06-26"}
        )
        coord = await _coord(hass, [chore])
        assert coord._is_chore_scheduled_for_date(chore, WED) is True
        assert coord.occurrence_origin(chore, WED) == MON

    async def test_disabled_chore_stays_off(self, hass):
        chore = Chore(name="Off", enabled=False, moved_occurrences={"2026-06-22": "2026-06-24"})
        coord = await _coord(hass, [chore])
        assert coord._is_chore_scheduled_for_date(chore, WED) is False


# ── Calendar entity projection + ICS ─────────────────────────────────────


class TestProjection:
    async def test_events_carry_occurrence_uid(self, hass):
        weekly = Chore(name="Bins", due_days=["monday"])
        one_off = Chore(name="Party", schedule_mode="one_shot", created_date="2026-06-23", assigned_to=["alex"])
        coord = await _coord(hass, [weekly, one_off])
        cal = _cal(coord)
        ev = _event(cal, MON, "Bins")
        assert ev.uid == f"taskmate-chore:{weekly.id}:2026-06-22"
        assert ev.recurrence_id == "2026-06-22"
        party = _event(cal, TUE, "Party")
        assert party.uid == f"taskmate-chore:{one_off.id}:2026-06-23"
        assert getattr(party, "recurrence_id", None) is None

    async def test_moved_event_keeps_uid_on_new_day(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], moved_occurrences={"2026-06-22": "2026-06-24"})
        coord = await _coord(hass, [chore])
        cal = _cal(coord)
        assert _chore_days(cal, MON, NEXT_MON, "Bins") == [WED, NEXT_MON]
        assert _event(cal, WED, "Bins").uid == f"taskmate-chore:{chore.id}:2026-06-22"

    async def test_removed_occurrence_gone_from_calendar_and_ics(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], moved_occurrences={"2026-06-22": ""})
        coord = await _coord(hass, [chore])
        assert _chore_days(_cal(coord), MON, NEXT_MON, "Bins") == [NEXT_MON]
        days = {e["start"] for e in ics.build_chore_events(coord, MON, NEXT_MON) if e["summary"].startswith("Bins")}
        assert days == {NEXT_MON}

    async def test_ics_follows_a_move(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], moved_occurrences={"2026-06-22": "2026-06-25"})
        coord = await _coord(hass, [chore])
        days = {e["start"] for e in ics.build_chore_events(coord, MON, NEXT_MON) if e["summary"] == "Bins — Alex"}
        assert days == {THU, NEXT_MON}

    def test_uid_parsing(self):
        assert _parse_occurrence_uid(_occurrence_uid("abc", MON), None) == ("abc", MON)
        assert _parse_occurrence_uid("taskmate-chore:abc", "20260622") == ("abc", MON)
        assert _parse_occurrence_uid("taskmate-chore:abc", "2026-06-22") == ("abc", MON)
        assert _parse_occurrence_uid("someone-else:abc:2026-06-22", None) is None
        assert _parse_occurrence_uid("taskmate-chore:abc", None) is None
        assert _parse_occurrence_uid("taskmate-chore:abc:not-a-date", None) is None


# ── Timed events start at the chore's due time (#993) ────────────────────


class TestDueTimeEvents:
    """A chore with a due_time shows as a 30-minute event starting then (#993)."""

    async def test_entity_event_starts_at_due_time(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], time_category="evening", due_time="17:30")
        coord = await _coord(hass, [chore])
        ev = _event(_cal(coord), MON, "Bins")
        assert (ev.start.hour, ev.start.minute) == (17, 30)
        assert ev.end - ev.start == dt.timedelta(minutes=30)
        assert ev.start.date() == MON and ev.start.tzinfo is not None

    async def test_anytime_chore_with_due_time_is_timed(self, hass):
        chore = Chore(name="Meds", due_days=["monday"], time_category="anytime", due_time="08:15")
        coord = await _coord(hass, [chore])
        ev = _event(_cal(coord), MON, "Meds")
        assert isinstance(ev.start, dt.datetime) and (ev.start.hour, ev.start.minute) == (8, 15)

    async def test_without_due_time_keeps_period_window(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], time_category="evening")
        coord = await _coord(hass, [chore])
        ev = _event(_cal(coord), MON, "Bins")
        assert (ev.start.hour, ev.end.hour) == (17, 21)

    async def test_invalid_due_time_falls_back_to_period(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], time_category="evening", due_time="junk")
        coord = await _coord(hass, [chore])
        ev = _event(_cal(coord), MON, "Bins")
        assert (ev.start.hour, ev.end.hour) == (17, 21)

    async def test_late_due_time_runs_past_midnight(self, hass):
        chore = Chore(name="Lock up", due_days=["monday"], time_category="evening", due_time="23:45")
        coord = await _coord(hass, [chore])
        ev = _event(_cal(coord), MON, "Lock up")
        assert ev.start.date() == MON and ev.end.date() == TUE
        assert (ev.end.hour, ev.end.minute) == (0, 15)

    async def test_ics_event_starts_at_due_time(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], time_category="evening", due_time="17:30")
        coord = await _coord(hass, [chore])
        [ev] = [e for e in ics.build_chore_events(coord, MON, MON) if e["summary"] == "Bins — Alex"]
        assert ev["all_day"] is False
        assert (ev["start"].hour, ev["start"].minute) == (17, 30)
        assert ev["end"] - ev["start"] == dt.timedelta(minutes=30)

    async def test_published_event_starts_at_due_time(self, hass):
        chore = Chore(
            name="Bins",
            due_days=["monday"],
            time_category="evening",
            due_time="17:30",
            assigned_to=["alex"],
        )
        coord = await _coord(hass, [chore])
        payload = coord._build_event_payload(chore, MON, "Bins — Alex")
        assert payload["start_date_time"] == "2026-06-22T17:30:00"
        assert payload["end_date_time"] == "2026-06-22T18:00:00"

    async def test_one_off_moved_by_calendar_keeps_the_new_time(self, hass):
        cal_coord = await _coord(hass)
        cal = _cal(cal_coord)
        await _run_as(PARENT, cal.async_create_event(dtstart=_at(WED, 17), dtend=_at(WED, 18), summary="Walk dog"))
        [chore] = cal_coord.storage.get_chores()
        uid = _occurrence_uid(chore.id, WED)
        start = dt.datetime.combine(THU, dt.time(9, 0), tzinfo=UTC)
        await _run_as(
            PARENT,
            cal.async_update_event(
                uid, {"dtstart": start, "dtend": start + dt.timedelta(minutes=30), "summary": "Walk dog"}
            ),
        )
        ev = _event(cal, THU, "Walk dog")
        assert (ev.start.hour, ev.start.minute) == (9, 0)

    async def test_series_occurrence_moved_keeps_due_time(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], time_category="evening", due_time="17:30")
        coord = await _coord(hass, [chore])
        cal = _cal(coord)
        start = dt.datetime.combine(WED, dt.time(17, 30), tzinfo=UTC)
        # Dragging the 17:30 event to Wednesday at the same time is a plain date move.
        await _run_as(
            PARENT,
            cal.async_update_event(
                _occurrence_uid(chore.id, MON),
                {"dtstart": start, "dtend": start + dt.timedelta(minutes=30), "summary": "Bins"},
                recurrence_id="2026-06-22",
            ),
        )
        assert coord.storage.get_chore(chore.id).moved_occurrences == {"2026-06-22": "2026-06-24"}
        ev = _event(cal, WED, "Bins")
        assert (ev.start.hour, ev.start.minute) == (17, 30)
        [ics_ev] = [e for e in ics.build_chore_events(coord, WED, WED) if e["summary"] == "Bins — Alex"]
        assert (ics_ev["start"].hour, ics_ev["start"].minute) == (17, 30)
        # A different time on a series is still the chore's, not the occurrence's.
        other = dt.datetime.combine(THU, dt.time(9, 0), tzinfo=UTC)
        with pytest.raises(FakeServiceValidationError) as err:
            await coord.async_move_chore_occurrence(chore.id, MON, THU, start_time=other.time(), all_day=False)
        assert err.value.translation_key == "calendar_time_follows_chore"


# ── Today's availability (cards, todo, reminders, completion gate) ───────


class TestAvailability:
    async def test_removed_today_hides_specific_days_chore(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], moved_occurrences={"2026-06-22": ""})
        coord = await _coord(hass, [chore])
        assert coord.is_chore_available_for_child(chore, "alex") is False
        assert coord._is_chore_completable_by_child(chore, "alex") is False
        assert coord.get_due_chores_for_child("alex") == []

    async def test_moved_onto_non_due_weekday_is_due(self, hass):
        # A Wednesday chore moved onto Monday (today).
        chore = Chore(name="Hoover", due_days=["wednesday"], moved_occurrences={"2026-06-24": "2026-06-22"})
        coord = await _coord(hass, [chore])
        assert coord._is_chore_completable_by_child(chore, "alex") is True
        assert [c.name for c in coord.get_due_chores_for_child("alex")] == ["Hoover"]
        assert coord._timed_start_allowed(chore, "alex") is True
        # ...and it's gone from Wednesday.
        dt_util_mock._now = _at(WED)
        assert coord._is_chore_completable_by_child(chore, "alex") is False

    async def test_recurring_moved_onto_today_opens(self, hass):
        chore = Chore(
            name="Car",
            schedule_mode="recurring",
            recurrence="weekly",
            recurrence_day="wednesday",
            moved_occurrences={"2026-06-24": "2026-06-22"},
        )
        coord = await _coord(hass, [chore])
        coord.storage.set_last_completed(chore.id, "alex", _at(dt.date(2026, 6, 17)).isoformat())
        assert coord.is_chore_available_for_child(chore, "alex") is True
        # Done today: closed for the rest of today.
        coord.storage.set_last_completed(chore.id, "alex", _at(MON).isoformat())
        assert coord.is_chore_available_for_child(chore, "alex") is False
        # Not on its old Wednesday either.
        dt_util_mock._now = _at(WED)
        assert coord.is_chore_available_for_child(chore, "alex") is False

    async def test_window_after_a_move_counts_from_the_original_day(self, hass):
        # Monthly on the 22nd; June's occurrence moved later, to the 30th, and
        # done there. July 22nd must still open — measured from June 22nd, not
        # June 30th.
        chore = Chore(
            name="Filters",
            schedule_mode="recurring",
            recurrence="monthly",
            recurrence_start="2026-05-22",
            moved_occurrences={"2026-06-22": "2026-06-30"},
        )
        coord = await _coord(hass, [chore])
        coord.storage.set_last_completed(chore.id, "alex", _at(dt.date(2026, 6, 30)).isoformat())
        dt_util_mock._now = _at(dt.date(2026, 7, 22))
        assert coord.is_chore_available_for_child(chore, "alex") is True

    async def test_sensor_record_flags_today_only_when_touched(self, hass):
        plain = Chore(name="Plain", due_days=["monday"])
        removed = Chore(name="Removed", due_days=["monday"], moved_occurrences={"2026-06-22": ""})
        moved_in = Chore(name="MovedIn", due_days=["friday"], moved_occurrences={"2026-06-26": "2026-06-22"})
        elsewhere = Chore(name="Elsewhere", due_days=["friday"], moved_occurrences={"2026-06-26": "2026-06-27"})
        stale = Chore(name="Stale", due_days=["friday"], moved_occurrences={"2026-04-03": ""})
        coord = await _coord(hass, [plain, removed, moved_in, elsewhere, stale])
        records = {
            r["name"]: r for r in _build_chores_list(coord, {"chores": coord.storage.get_chores(), "hass": hass})
        }
        assert "occ_today" not in records["Plain"] and "moved_occurrences" not in records["Plain"]
        assert records["Removed"]["occ_today"] is False
        assert records["MovedIn"]["occ_today"] is True
        assert "occ_today" not in records["Elsewhere"]
        assert records["Elsewhere"]["moved_occurrences"] == {"2026-06-26": "2026-06-27"}
        # Long-past moves stay out of the attribute (16 KB budget).
        assert "moved_occurrences" not in records["Stale"]


# ── Streaks, mandatory misses, reports ───────────────────────────────────


class TestHistoryPaths:
    async def test_streak_due_set_follows_moves(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], moved_occurrences={"2026-06-22": "2026-06-24"})
        coord = await _coord(hass, [chore])
        assert coord._due_chore_ids_for_child("alex", MON, include_rotation=True) == set()
        assert coord._due_chore_ids_for_child("alex", WED, include_rotation=True) == {chore.id}

    async def test_no_mandatory_miss_for_a_removed_day(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], mandatory=True, moved_occurrences={"2026-06-22": ""})
        coord = await _coord(hass, [chore])
        coord._effective_period_for = MagicMock(return_value="anytime")
        assert await coord.async_detect_mandatory_misses("anytime", MON) == 0
        assert coord.storage.get_mandatory_misses() == []

    async def test_reports_follow_moves(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], moved_occurrences={"2026-06-22": "2026-06-24"})
        coord = await _coord(hass, [chore])
        assert coord._chore_falls_on(chore, MON) is False
        assert coord._chore_falls_on(chore, WED) is True
        # Two Mondays in the window, one moved within it: still two.
        assert coord._expected_occurrences(chore, MON, NEXT_MON) == 2
        chore.moved_occurrences = {"2026-06-22": ""}
        assert coord._expected_occurrences(chore, MON, NEXT_MON) == 1


# ── Coordinator edits ────────────────────────────────────────────────────


class TestCoordinatorEdits:
    async def test_add_one_off_from_calendar(self, hass):
        coord = await _coord(hass)
        chore = await coord.async_calendar_add_chore("alex", "  Tidy shed ", WED, start_time=dt.time(15, 30))
        stored = coord.storage.get_chore(chore.id)
        assert stored.name == "Tidy shed"
        assert stored.schedule_mode == "one_shot"
        assert stored.created_date == "2026-06-24"
        assert stored.assigned_to == ["alex"]
        assert stored.points == 10
        assert stored.due_time == "15:30"
        assert stored.time_category == "afternoon"

    async def test_all_day_one_off_is_anytime(self, hass):
        coord = await _coord(hass)
        chore = await coord.async_calendar_add_chore("alex", "Tidy", WED)
        assert chore.time_category == "anytime" and chore.due_time == ""

    @pytest.mark.parametrize(
        ("name", "day", "key"),
        [("", WED, "calendar_empty_title"), ("Late", dt.date(2026, 6, 21), "calendar_past_date")],
    )
    async def test_add_refusals(self, hass, name, day, key):
        coord = await _coord(hass)
        with pytest.raises(FakeServiceValidationError) as err:
            await coord.async_calendar_add_chore("alex", name, day)
        assert err.value.translation_key == key
        assert coord.storage.get_chores() == []

    async def test_move_and_move_back(self, hass):
        chore = Chore(name="Bins", due_days=["monday"])
        coord = await _coord(hass, [chore])
        await coord.async_move_chore_occurrence(chore.id, MON, WED, all_day=True, summary="Bins")
        assert coord.storage.get_chore(chore.id).moved_occurrences == {"2026-06-22": "2026-06-24"}
        await coord.async_move_chore_occurrence(chore.id, MON, THU, all_day=True)
        assert coord.storage.get_chore(chore.id).moved_occurrences == {"2026-06-22": "2026-06-25"}
        await coord.async_move_chore_occurrence(chore.id, MON, MON, all_day=True)
        assert coord.storage.get_chore(chore.id).moved_occurrences == {}

    async def test_move_onto_an_existing_occurrence_refused(self, hass):
        chore = Chore(name="Daily", due_days=[])
        coord = await _coord(hass, [chore])
        with pytest.raises(FakeServiceValidationError) as err:
            await coord.async_move_chore_occurrence(chore.id, MON, TUE, all_day=True)
        assert err.value.translation_key == "calendar_already_scheduled"
        assert err.value.translation_placeholders == {"chore": "Daily", "date": "2026-06-23"}

    async def test_series_title_and_time_are_the_chores(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], time_category="morning")
        coord = await _coord(hass, [chore])
        with pytest.raises(FakeServiceValidationError) as err:
            await coord.async_move_chore_occurrence(chore.id, MON, WED, start_time=dt.time(6, 0), summary="Recycling")
        assert err.value.translation_key == "calendar_rename_series"
        with pytest.raises(FakeServiceValidationError) as err:
            await coord.async_move_chore_occurrence(chore.id, MON, WED, start_time=dt.time(8, 0), all_day=False)
        assert err.value.translation_key == "calendar_time_follows_chore"
        # Same start time as the period window: a plain date move.
        await coord.async_move_chore_occurrence(chore.id, MON, WED, start_time=dt.time(6, 0), all_day=False)
        assert coord.storage.get_chore(chore.id).moved_occurrences == {"2026-06-22": "2026-06-24"}

    async def test_past_moves_refused(self, hass):
        chore = Chore(name="Bins", due_days=["sunday"])
        coord = await _coord(hass, [chore])
        with pytest.raises(FakeServiceValidationError) as err:
            await coord.async_move_chore_occurrence(chore.id, dt.date(2026, 6, 21), WED, all_day=True)
        assert err.value.translation_key == "calendar_past_date"

    async def test_one_off_move_changes_date_title_and_time(self, hass):
        chore = Chore(name="Party", schedule_mode="one_shot", created_date="2026-06-23", assigned_to=["alex"])
        coord = await _coord(hass, [chore])
        await coord.async_move_chore_occurrence(
            chore.id, TUE, THU, start_time=dt.time(18, 0), all_day=False, summary="Birthday party"
        )
        stored = coord.storage.get_chore(chore.id)
        assert stored.created_date == "2026-06-25"
        assert stored.name == "Birthday party"
        assert stored.due_time == "18:00" and stored.time_category == "evening"
        assert stored.moved_occurrences == {}

    async def test_remove_one_day_of_a_series(self, hass):
        chore = Chore(name="Bins", due_days=["monday"])
        coord = await _coord(hass, [chore])
        await coord.async_remove_chore_occurrence(chore.id, NEXT_MON)
        stored = coord.storage.get_chore(chore.id)
        assert stored.moved_occurrences == {"2026-06-29": ""}
        assert stored.enabled is True

    async def test_remove_one_off_switches_it_off(self, hass):
        chore = Chore(name="Party", schedule_mode="one_shot", created_date="2026-06-23")
        coord = await _coord(hass, [chore])
        await coord.async_remove_chore_occurrence(chore.id, TUE)
        assert coord.storage.get_chore(chore.id).enabled is False

    async def test_old_entries_are_pruned_on_write(self, hass):
        chore = Chore(
            name="Bins", due_days=["monday"], moved_occurrences={"2026-03-02": "", "2026-03-09": "2026-03-10"}
        )
        coord = await _coord(hass, [chore])
        await coord.async_remove_chore_occurrence(chore.id, NEXT_MON)
        assert coord.storage.get_chore(chore.id).moved_occurrences == {"2026-06-29": ""}

    async def test_edits_republish_to_external_calendars(self, hass):
        chore = Chore(name="Bins", due_days=["monday"], publish_calendar_entities=["calendar.family"])
        coord = await _coord(hass, [chore])
        coord._cleanup_chore_from_calendars = AsyncMock()
        coord._publish_chore_to_calendars = AsyncMock()
        await coord.async_move_chore_occurrence(chore.id, MON, WED, all_day=True)
        coord._cleanup_chore_from_calendars.assert_awaited()
        coord._publish_chore_to_calendars.assert_awaited()


# ── Entity: permissions, create / update / delete ────────────────────────


def _run_as(user_id, coro):
    """Await ``coro`` as if it arrived on a websocket connection of ``user_id``."""

    async def _inner():
        current_connection.set(SimpleNamespace(user=SimpleNamespace(id=user_id)) if user_id else None)
        return await coro

    return asyncio.get_running_loop().create_task(_inner(), context=contextvars.copy_context())


class TestEntity:
    async def test_supported_features(self, hass):
        coord = await _coord(hass)
        flags = _cal(coord)._attr_supported_features
        assert flags & 1 and flags & 2 and flags & 4

    @pytest.mark.parametrize("user_id", [ADMIN, PARENT])
    async def test_parent_or_admin_can_create(self, hass, user_id):
        coord = await _coord(hass)
        cal = _cal(coord)
        await _run_as(user_id, cal.async_create_event(dtstart=WED, dtend=THU, summary="Rake leaves"))
        [chore] = coord.storage.get_chores()
        assert chore.name == "Rake leaves" and chore.assigned_to == ["alex"]
        [entry] = coord.storage.get_audit_log()
        assert entry["action"] == "calendar.create_event"
        assert entry["user_id"] == user_id
        assert entry["target"] == "Alex: Rake leaves (2026-06-24)"

    async def test_child_user_refused_everywhere(self, hass):
        chore = Chore(name="Bins", due_days=["monday"])
        coord = await _coord(hass, [chore])
        cal = _cal(coord)
        uid = _occurrence_uid(chore.id, MON)
        with pytest.raises(FakeUnauthorized):
            await _run_as(KID, cal.async_create_event(dtstart=WED, dtend=THU, summary="Sneaky"))
        with pytest.raises(FakeUnauthorized):
            await _run_as(KID, cal.async_update_event(uid, {"dtstart": WED, "dtend": THU, "summary": "Bins"}))
        with pytest.raises(FakeUnauthorized):
            await _run_as(KID, cal.async_delete_event(uid))
        assert [c.name for c in coord.storage.get_chores()] == ["Bins"]
        assert coord.storage.get_chore(chore.id).moved_occurrences == {}

    async def test_service_context_user_is_checked(self, hass):
        coord = await _coord(hass)
        cal = _cal(coord)
        cal.async_set_context(SimpleNamespace(user_id=KID))
        with pytest.raises(FakeUnauthorized):
            await cal.async_create_event(dtstart=WED, dtend=THU, summary="Sneaky")
        cal.async_set_context(SimpleNamespace(user_id=PARENT))
        await cal.async_create_event(dtstart=WED, dtend=THU, summary="Fine")
        assert [c.name for c in coord.storage.get_chores()] == ["Fine"]

    async def test_context_is_single_use(self, hass):
        # An admin's get_events (or earlier edit) must not vouch for a later
        # websocket edit by someone else.
        coord = await _coord(hass)
        cal = _cal(coord)
        cal.async_set_context(SimpleNamespace(user_id=ADMIN))
        await cal.async_get_events(hass, _at(MON), _at(THU))
        with pytest.raises(FakeUnauthorized):
            await _run_as(KID, cal.async_create_event(dtstart=WED, dtend=THU, summary="Sneaky"))

    async def test_both_doors_must_agree(self, hass):
        coord = await _coord(hass)
        cal = _cal(coord)
        cal.async_set_context(SimpleNamespace(user_id=ADMIN))
        with pytest.raises(FakeUnauthorized):
            await _run_as(KID, cal.async_create_event(dtstart=WED, dtend=THU, summary="Sneaky"))

    async def test_automation_without_user_is_trusted(self, hass):
        coord = await _coord(hass)
        cal = _cal(coord)
        cal.async_set_context(SimpleNamespace(user_id=None))
        await cal.async_create_event(dtstart=WED, dtend=THU, summary="From automation")
        assert coord.storage.get_audit_log()[0]["user_id"] == ""

    async def test_timed_create_sets_due_time(self, hass):
        coord = await _coord(hass)
        cal = _cal(coord)
        await _run_as(PARENT, cal.async_create_event(dtstart=_at(WED, 7), dtend=_at(WED, 8), summary="Walk dog"))
        [chore] = coord.storage.get_chores()
        assert chore.due_time == "07:00" and chore.time_category == "morning"

    @pytest.mark.parametrize(
        ("extra", "key"),
        [
            ({"rrule": "FREQ=WEEKLY"}, "calendar_repeating_create"),
            ({"description": "taskmate:chore:abc"}, "calendar_own_event"),
        ],
    )
    async def test_create_refusals(self, hass, extra, key):
        coord = await _coord(hass)
        cal = _cal(coord)
        with pytest.raises(FakeServiceValidationError) as err:
            await _run_as(PARENT, cal.async_create_event(dtstart=WED, dtend=THU, summary="X", **extra))
        assert err.value.translation_key == key
        assert coord.storage.get_chores() == []

    async def test_move_single_occurrence(self, hass):
        chore = Chore(name="Bins", due_days=["monday"])
        coord = await _coord(hass, [chore])
        cal = _cal(coord)
        uid = _occurrence_uid(chore.id, MON)
        await _run_as(
            PARENT,
            cal.async_update_event(uid, {"dtstart": WED, "dtend": THU, "summary": "Bins"}, recurrence_id="2026-06-22"),
        )
        assert _chore_days(cal, MON, NEXT_MON, "Bins") == [WED, NEXT_MON]
        assert coord.storage.get_audit_log()[0]["action"] == "calendar.move_event"
        # Moved again: same uid, found on its new day.
        await _run_as(PARENT, cal.async_update_event(uid, {"dtstart": THU, "dtend": THU, "summary": "Bins"}))
        assert _chore_days(cal, MON, NEXT_MON, "Bins") == [THU, NEXT_MON]

    @pytest.mark.parametrize("kwargs", [{"recurrence_range": "THISANDFUTURE"}, {"rrule": "FREQ=WEEKLY"}])
    async def test_series_move_refused(self, hass, kwargs):
        chore = Chore(name="Bins", due_days=["monday"])
        coord = await _coord(hass, [chore])
        cal = _cal(coord)
        event = {"dtstart": WED, "dtend": THU, "summary": "Bins"}
        if "rrule" in kwargs:
            event["rrule"] = kwargs["rrule"]
            call = cal.async_update_event(_occurrence_uid(chore.id, MON), event)
        else:
            call = cal.async_update_event(_occurrence_uid(chore.id, MON), event, **kwargs)
        with pytest.raises(FakeServiceValidationError) as err:
            await _run_as(PARENT, call)
        assert err.value.translation_key == "calendar_series_not_supported"
        assert coord.storage.get_chore(chore.id).moved_occurrences == {}

    async def test_series_delete_refused(self, hass):
        chore = Chore(name="Bins", due_days=["monday"])
        coord = await _coord(hass, [chore])
        with pytest.raises(FakeServiceValidationError) as err:
            await _run_as(
                PARENT, _cal(coord).async_delete_event(_occurrence_uid(chore.id, MON), recurrence_range="THISANDFUTURE")
            )
        assert err.value.translation_key == "calendar_series_not_supported"

    async def test_delete_single_occurrence(self, hass):
        chore = Chore(name="Bins", due_days=["monday"])
        coord = await _coord(hass, [chore])
        cal = _cal(coord)
        await _run_as(ADMIN, cal.async_delete_event(_occurrence_uid(chore.id, NEXT_MON), recurrence_id="2026-06-29"))
        assert _chore_days(cal, MON, dt.date(2026, 7, 6), "Bins") == [MON, dt.date(2026, 7, 6)]
        assert coord.storage.get_audit_log()[0]["action"] == "calendar.delete_event"

    async def test_other_childs_occurrence_is_not_editable_here(self, hass):
        chore = Chore(name="Sam's", due_days=[], assigned_to=["sam"])
        coord = await _coord(hass, [chore])
        with pytest.raises(FakeServiceValidationError) as err:
            await _run_as(PARENT, _cal(coord, "alex").async_delete_event(_occurrence_uid(chore.id, MON)))
        assert err.value.translation_key == "calendar_unknown_event"
        assert coord.storage.get_chore(chore.id).moved_occurrences == {}

    async def test_unknown_uid(self, hass):
        coord = await _coord(hass)
        with pytest.raises(FakeServiceValidationError) as err:
            await _run_as(PARENT, _cal(coord).async_delete_event("some-other-calendar-uid"))
        assert err.value.translation_key == "calendar_unknown_event"


# ── Through Home Assistant's calendar/event/* websocket commands ─────────
#
# A faithful replica of homeassistant/components/calendar/__init__.py's
# handle_calendar_event_create / _update / _delete (the calendar panel's
# door): feature check, then the entity method, with HomeAssistantError (and,
# for update/delete, ValueError) reported as a "failed" error. The handlers
# run inside the connection's context, where current_connection is set.


class _Conn:
    def __init__(self, user_id):
        self.user = SimpleNamespace(id=user_id)
        self.results: list = []
        self.errors: list = []

    def send_result(self, msg_id, result=None):
        self.results.append(msg_id)

    def send_error(self, msg_id, code, message):
        self.errors.append((msg_id, code, message))


_HA_ERRORS = (FakeServiceValidationError, FakeUnauthorized)


async def _ws(entity, conn, msg):
    async def _handle():
        current_connection.set(conn)
        feature = {"calendar/event/create": 1, "calendar/event/delete": 2, "calendar/event/update": 4}[msg["type"]]
        if not entity.supported_features & feature:
            conn.send_error(msg["id"], "not_supported", "Calendar does not support it")
            return
        try:
            if msg["type"] == "calendar/event/create":
                await entity.async_create_event(**msg["event"])
            elif msg["type"] == "calendar/event/delete":
                await entity.async_delete_event(
                    msg["uid"], recurrence_id=msg.get("recurrence_id"), recurrence_range=msg.get("recurrence_range")
                )
            else:
                await entity.async_update_event(
                    msg["uid"],
                    msg["event"],
                    recurrence_id=msg.get("recurrence_id"),
                    recurrence_range=msg.get("recurrence_range"),
                )
        except (*_HA_ERRORS, ValueError) as ex:
            conn.send_error(msg["id"], "failed", ex.translation_key if hasattr(ex, "translation_key") else str(ex))
        else:
            conn.send_result(msg["id"])

    await asyncio.get_running_loop().create_task(_handle(), context=contextvars.copy_context())


class TestWebsocketCommands:
    async def test_full_round_trip(self, hass):
        chore = Chore(name="Bins", due_days=["monday"])
        coord = await _coord(hass, [chore])
        cal = _cal(coord)
        cal.supported_features = cal._attr_supported_features
        parent = _Conn(PARENT)

        await _ws(
            cal,
            parent,
            {"id": 1, "type": "calendar/event/create", "event": {"dtstart": TUE, "dtend": WED, "summary": "Swim kit"}},
        )
        ev = _event(cal, MON, "Bins")
        await _ws(
            cal,
            parent,
            {
                "id": 2,
                "type": "calendar/event/update",
                "uid": ev.uid,
                "recurrence_id": ev.recurrence_id,
                "event": {"dtstart": THU, "dtend": dt.date(2026, 6, 26), "summary": "Bins"},
            },
        )
        await _ws(
            cal,
            parent,
            {
                "id": 3,
                "type": "calendar/event/delete",
                "uid": _occurrence_uid(chore.id, NEXT_MON),
                "recurrence_id": "2026-06-29",
            },
        )
        await _ws(
            cal,
            parent,
            {
                "id": 4,
                "type": "calendar/event/update",
                "uid": ev.uid,
                "recurrence_range": "THISANDFUTURE",
                "event": {"dtstart": WED, "dtend": THU, "summary": "Bins"},
            },
        )
        assert parent.results == [1, 2, 3]
        assert parent.errors == [(4, "failed", "calendar_series_not_supported")]

        assert _chore_days(cal, MON, dt.date(2026, 7, 6), "Bins") == [THU, dt.date(2026, 7, 6)]
        assert _chore_days(cal, MON, NEXT_MON, "Swim kit") == [TUE]
        assert [e["action"] for e in coord.storage.get_audit_log()] == [
            "calendar.delete_event",
            "calendar.move_event",
            "calendar.create_event",
        ]

        kid = _Conn(KID)
        await _ws(
            cal, kid, {"id": 5, "type": "calendar/event/delete", "uid": _occurrence_uid(chore.id, dt.date(2026, 7, 6))}
        )
        assert kid.results == [] and kid.errors[0][:2] == (5, "failed")
        assert _chore_days(cal, MON, dt.date(2026, 7, 6), "Bins") == [THU, dt.date(2026, 7, 6)]
