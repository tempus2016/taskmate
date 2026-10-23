"""Bin-day chores: the evening before a collection, a chore per bin."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.taskmate.coord_bin_days import bin_emoji

from .test_completion_eligibility import _make_system, run

BINS = "custom_components.taskmate.coord_bin_days.dt_util"
CHORES = "custom_components.taskmate.coord_chores.dt_util"
TZ = dt.UTC


def _when(day=20, hour=18, minute=5):
    return dt.datetime(2026, 10, day, hour, minute, tzinfo=TZ)


def _system(events=None, mode="first_come", bring_in=False):
    coord, storage, mod = _make_system()
    coord.hass.bus = MagicMock()
    coord.badges = None
    calendar_events = events if events is not None else [{"summary": "Recycling", "start": "2026-10-21"}]
    calls = []

    async def fake_call(domain, service, data, blocking=False, return_response=False):
        calls.append((domain, service, data))
        return {data["entity_id"]: {"events": list(calendar_events)}}

    coord.hass.services = MagicMock()
    coord.hass.services.async_call = AsyncMock(side_effect=fake_call)
    storage.set_setting("bin_day_enabled", True)
    storage.set_setting("bin_day_calendars", ["calendar.bins"])
    storage.set_setting("bin_day_mode", mode)
    storage.set_setting("bin_day_points", 7)
    storage.set_setting("bin_day_bring_in", bring_in)
    with patch.object(mod.dt_util, "now", return_value=_when()):
        kid = run(coord.async_add_child("Vaiha"))
        leo = run(coord.async_add_child("Leo"))
    return coord, storage, mod, kid, leo, calls, calendar_events


def _tick(coord, mod, when):
    with (
        patch(f"{BINS}.now", return_value=when),
        patch(f"{CHORES}.now", return_value=when),
        patch.object(mod.dt_util, "now", return_value=when),
        patch(f"{BINS}.as_local", side_effect=lambda d: d),
        patch(f"{BINS}.start_of_local_day", side_effect=lambda d: d.replace(hour=0, minute=0, second=0, microsecond=0)),
        patch(f"{CHORES}.as_local", side_effect=lambda d: d),
    ):
        return run(coord.async_check_bin_days())


def _bin_chores(storage):
    return [c for c in storage.get_chores() if "out" in c.name or " in" in c.name]


class TestPutOut:
    def test_nothing_happens_before_the_put_out_time(self):
        coord, storage, mod, *_rest, calls, _events = _system()
        assert _tick(coord, mod, _when(hour=17, minute=59)) == 0
        assert calls == []

    def test_a_chore_per_bin_the_evening_before(self):
        events = [
            {"summary": "Recycling", "start": "2026-10-21"},
            {"summary": "General waste", "start": {"date": "2026-10-21"}},
        ]
        coord, storage, mod, kid, leo, _calls, _ev = _system(events=events)
        assert _tick(coord, mod, _when()) == 2
        names = sorted(c.name for c in _bin_chores(storage))
        assert names == ["♻️ Put the Recycling out", "🗑️ Put the General waste out"]
        chore = _bin_chores(storage)[0]
        assert chore.schedule_mode == "one_shot" and chore.points == 7 and chore.time_category == "anytime"
        assert chore.assignment_mode == "first_come" and sorted(chore.assigned_to) == sorted([kid.id, leo.id])
        assert chore.deadline_at.startswith("2026-10-20T23:59")
        evt = [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == "taskmate_bin_day"]
        assert {e["kind"] for e in evt} == {"put_out"}

    def test_each_collection_only_raises_one_chore(self):
        coord, storage, mod, *_rest = _system()
        _tick(coord, mod, _when())
        _tick(coord, mod, _when(minute=30))
        _tick(coord, mod, _when(hour=21))
        assert len(_bin_chores(storage)) == 1

    def test_calendar_is_reread_at_most_every_fifteen_minutes(self):
        coord, _storage, mod, _kid, _leo, calls, _events = _system()
        _tick(coord, mod, _when(minute=5))
        _tick(coord, mod, _when(minute=10))
        _tick(coord, mod, _when(minute=21))
        assert len(calls) == 2

    def test_events_not_on_tomorrow_are_ignored(self):
        coord, storage, mod, *_rest = _system(events=[{"summary": "Recycling", "start": "2026-10-23"}])
        assert _tick(coord, mod, _when()) == 0
        assert _bin_chores(storage) == []

    def test_rotate_hands_each_collection_to_the_next_child(self):
        coord, storage, mod, kid, leo, _calls, events = _system(mode="rotate")
        _tick(coord, mod, _when(day=20))
        events[:] = [{"summary": "Garden", "start": "2026-10-28"}]
        _tick(coord, mod, _when(day=27))
        chores = _bin_chores(storage)
        assert [c.assigned_to for c in chores] == [[kid.id], [leo.id]]
        assert chores[1].name.startswith("🌿")

    def test_disabled_or_no_calendar_does_nothing(self):
        coord, storage, mod, *_rest, calls, _events = _system()
        storage.set_setting("bin_day_calendars", [])
        assert _tick(coord, mod, _when()) == 0
        storage.set_setting("bin_day_calendars", ["calendar.bins"])
        storage.set_setting("bin_day_enabled", False)
        assert _tick(coord, mod, _when()) == 0
        assert calls == []


class TestBringIn:
    def test_bring_in_chore_appears_on_collection_day_once(self):
        coord, storage, mod, *_rest = _system(bring_in=True)
        _tick(coord, mod, _when())
        assert _tick(coord, mod, _when(day=21, hour=15)) == 0
        assert _tick(coord, mod, _when(day=21, hour=16, minute=1)) == 1
        assert _tick(coord, mod, _when(day=21, hour=17)) == 0
        assert [c.name for c in _bin_chores(storage)][-1] == "♻️ Bring the Recycling in"

    def test_no_bring_in_when_switched_off(self):
        coord, storage, mod, *_rest = _system(bring_in=False)
        _tick(coord, mod, _when())
        assert _tick(coord, mod, _when(day=21, hour=16, minute=1)) == 0


class TestEmojiAndPreview:
    def test_emoji_by_bin_name(self):
        assert bin_emoji("Blue bin (paper)") == "♻️"
        assert bin_emoji("Brown bin") == "🌿"
        assert bin_emoji("Glass") == "🍾"
        assert bin_emoji("Black bag") == "🗑️"

    def test_preview_lists_upcoming_collections_without_duplicates(self):
        events = [
            {"summary": "Recycling", "start": "2026-10-21"},
            {"summary": "recycling", "start": "2026-10-21"},
            {"summary": "Glass", "start": "2026-10-24"},
        ]
        coord, _storage, mod, *_rest = _system(events=events)
        with (
            patch(f"{BINS}.now", return_value=_when()),
            patch(f"{BINS}.start_of_local_day", side_effect=lambda d: d.replace(hour=0, minute=0)),
        ):
            preview = run(coord.async_bin_day_preview())
        assert [(p["date"], p["emoji"]) for p in preview] == [("2026-10-21", "♻️"), ("2026-10-24", "🍾")]
