"""Season event packs: windows, install / retire / re-enable, advent, settings, sensor."""

from __future__ import annotations

import datetime as dt
import json
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from custom_components.taskmate import websocket as ws
from custom_components.taskmate import websocket_panel_tools
from custom_components.taskmate.coord_season_packs import SEASON_PACKS_SECTION
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, ChoreCompletion
from custom_components.taskmate.season_packs import PACKS, pack_contents, pack_string_keys, read_strings
from custom_components.taskmate.seasons import (
    active_season,
    current_window,
    easter_sunday,
    next_window,
    season_window,
)
from custom_components.taskmate.sensor import TaskMateOverallStatsSensor, _compute_common
from custom_components.taskmate.storage import TaskMateStorage

from .conftest import dt_util_mock
from .test_setup_wizard import LOCALES, _ws_env, run

# ── Windows ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("year", "sunday"),
    [
        (2008, date(2008, 3, 23)),
        (2019, date(2019, 4, 21)),
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
        (2038, date(2038, 4, 25)),
    ],
)
def test_easter_sunday(year, sunday):
    assert easter_sunday(year) == sunday


def test_easter_window_is_the_week_up_to_sunday():
    assert season_window("easter", 2026, {}) == (date(2026, 3, 30), date(2026, 4, 5))
    assert current_window("easter", date(2026, 3, 29), {}) is None
    assert current_window("easter", date(2026, 4, 5), {}) == (date(2026, 3, 30), date(2026, 4, 5))
    assert current_window("easter", date(2026, 4, 6), {}) is None


def test_back_to_school_needs_a_date_and_runs_14_days():
    assert season_window("back_to_school", 2026, {}) is None
    assert next_window("back_to_school", date(2026, 8, 1), {}) is None
    settings = {"season_school_start": "2026-08-19"}
    assert current_window("back_to_school", date(2026, 9, 1), settings) == (date(2026, 8, 19), date(2026, 9, 1))
    assert current_window("back_to_school", date(2026, 9, 2), settings) is None
    assert next_window("back_to_school", date(2026, 8, 1), settings) == (date(2026, 8, 19), date(2026, 9, 1))
    # A date in the past has no next window.
    assert next_window("back_to_school", date(2026, 10, 1), settings) is None
    assert season_window("back_to_school", 2026, {"season_school_start": "junk"}) is None


def test_back_to_school_window_runs_over_new_year():
    settings = {"season_school_start": "2026-12-28"}
    assert current_window("back_to_school", date(2027, 1, 5), settings) == (date(2026, 12, 28), date(2027, 1, 10))


def test_next_window_wraps_to_next_year():
    assert next_window("christmas", date(2026, 12, 27), {}) == (date(2027, 12, 1), date(2027, 12, 26))
    assert next_window("halloween", date(2026, 10, 25), {}) == (date(2026, 10, 24), date(2026, 10, 31))


def test_new_themes_follow_their_windows():
    on = {"seasonal_easter": True, "seasonal_back_to_school": True, "season_school_start": "2026-08-25"}
    assert active_season(on, date(2026, 4, 1)) == "easter"
    assert active_season(on, date(2026, 8, 26)) == "back_to_school"
    # Back to school wins over Summer on a day both are on.
    assert active_season({**on, "seasonal_summer": True}, date(2026, 8, 26)) == "back_to_school"
    assert active_season({"seasonal_back_to_school": True}, date(2026, 8, 26)) == ""


# ── Pack data ────────────────────────────────────────────────────────────────


def test_every_pack_string_is_named_in_every_locale():
    keys = pack_string_keys()
    for path in LOCALES:
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = [k for k in keys if not str(data.get(k, "")).strip()]
        assert not missing, f"{path.name} lacks {missing}"


def test_pack_numbers_are_fixed_integers():
    for pack in PACKS.values():
        for chore in pack["chores"].values():
            assert isinstance(chore["points"], int) and chore["points"] > 0
        for kind, field in (("reward", "cost"), ("quest", "bonus"), ("badge", "bonus"), ("challenge", "bonus")):
            if kind in pack:
                assert isinstance(pack[kind][field], int)
        if "quest" in pack:
            assert all(step in pack["chores"] for step in pack["quest"]["steps"])
    assert sum(1 for k in PACKS["christmas"]["chores"] if k.startswith("advent_")) == 24
    assert PACKS["halloween"]["reward"]["cost"] == 40
    assert PACKS["christmas"]["reward"]["cost"] == 60


def test_pack_contents_shape():
    kinds = [c["kind"] for c in pack_contents("christmas")]
    assert kinds == ["advent", "quest", "chores", "reward", "badge"]
    assert pack_contents("easter")[0] == {"kind": "hunt", "count": 7, "points": 5}
    assert pack_contents("nope") == []


def test_names_read_in_the_family_language():
    de = read_strings("de")
    assert de["season_pack.halloween.carve_pumpkin"] == "Kürbis schnitzen"
    # pt-BR overlays pt, which overlays English.
    assert read_strings("pt-BR")["season_pack.christmas.advent_9"] == "Escrever um cartão para a vovó"
    assert read_strings("xx")["season_pack.halloween.sort_sweets"] == "Sort the sweets"


# ── Lifecycle ────────────────────────────────────────────────────────────────


@pytest.fixture
def coord():
    hass = MagicMock()
    hass.config.language = "en"
    hass.async_add_executor_job = AsyncMock(side_effect=lambda fn, *a: fn(*a))
    storage = TaskMateStorage(hass, "test_entry")
    storage._store = MagicMock()
    storage._store.async_load = AsyncMock(return_value=None)
    storage._store.async_save = AsyncMock()
    storage._store.async_delay_save = MagicMock()
    run(storage.async_load())
    c = object.__new__(TaskMateCoordinator)
    c.hass = hass
    c.storage = storage
    c.async_refresh = AsyncMock()
    c.badges = MagicMock()
    c.badges.award_manually = AsyncMock()
    for kid in (Child(name="Malia", id="k1"), Child(name="Vaiha", id="k2"), Child(name="Mum", id="a1", is_adult=True)):
        storage.add_child(kid)
    return c


def _on(coord, *seasons, **extra):
    for season in seasons:
        coord.storage.set_setting(f"season_pack_{season}", True)
    for key, value in extra.items():
        coord.storage.set_setting(key, value)


def _pack_items(coord, season):
    return coord.storage.data[SEASON_PACKS_SECTION][season]["items"]


def _counts(coord):
    return (
        len(coord.storage.get_chores()),
        len(coord.storage.get_rewards()),
        len(coord.storage.get_quests()),
        len(coord.storage.get_challenges()),
        len([b for b in coord.storage.get_badges() if not b.builtin]),
    )


def test_off_pack_installs_nothing(coord):
    assert run(coord.async_sync_season_packs(date(2026, 10, 25))) == []
    assert _counts(coord) == (0, 0, 0, 0, 0)


def test_pack_installs_once_in_its_window_with_one_refresh(coord):
    _on(coord, "halloween")
    assert run(coord.async_sync_season_packs(date(2026, 10, 20))) == []  # before the window
    assert run(coord.async_sync_season_packs(date(2026, 10, 24))) == ["halloween"]
    assert _counts(coord) == (5, 1, 1, 0, 1)
    assert coord.async_refresh.await_count == 1
    chore = next(c for c in coord.storage.get_chores() if c.template_id == "season.halloween.carve_pumpkin")
    assert chore.name == "Carve the pumpkin"
    assert chore.points == 10
    # Grown-ups are left out.
    assert chore.assigned_to == ["k1", "k2"]
    reward = coord.storage.get_rewards()[0]
    assert (reward.name, reward.cost, reward.expires_at) == ("Pick the movie", 40, "2026-11-01")
    quest = coord.storage.get_quests()[0]
    assert quest.name == "Pumpkin Patrol" and len(quest.steps) == 5
    # Idempotent: a restart, a second tick, the next day.
    for day in (date(2026, 10, 24), date(2026, 10, 25), date(2026, 10, 31)):
        assert run(coord.async_sync_season_packs(day)) == []
    assert _counts(coord) == (5, 1, 1, 0, 1)


def test_install_survives_a_restart(coord):
    _on(coord, "halloween")
    run(coord.async_sync_season_packs(date(2026, 10, 26)))
    saved = coord.storage.data
    # A new storage loading the same data (HA restarted).
    storage = TaskMateStorage(coord.hass, "test_entry")
    storage._store = MagicMock()
    storage._store.async_load = AsyncMock(return_value=json.loads(json.dumps(saved, default=str)))
    storage._store.async_save = AsyncMock()
    storage._store.async_delay_save = MagicMock()
    run(storage.async_load())
    coord.storage = storage
    assert run(coord.async_sync_season_packs(date(2026, 10, 27))) == []
    assert _counts(coord) == (5, 1, 1, 0, 1)


def test_names_follow_the_ha_language(coord):
    coord.hass.config.language = "fr"
    _on(coord, "halloween")
    run(coord.async_sync_season_packs(date(2026, 10, 26)))
    assert "Sculpter la citrouille" in {c.name for c in coord.storage.get_chores()}


def test_window_end_hides_and_next_year_brings_back_the_same_items(coord):
    _on(coord, "halloween")
    run(coord.async_sync_season_packs(date(2026, 10, 30)))
    ids = {c.id for c in coord.storage.get_chores()}
    quest = coord.storage.get_quests()[0]
    coord.storage.set_quest_child_progress(quest.id, "k1", {"step": 5, "done": True})

    assert run(coord.async_sync_season_packs(date(2026, 11, 1))) == ["halloween"]
    assert all(not c.enabled for c in coord.storage.get_chores())
    assert not coord.storage.get_quests()[0].active
    assert coord.storage.get_rewards()[0].expires_at == "2026-11-01"
    assert coord.season_pack_item_ids("reward", state="retired") == {coord.storage.get_rewards()[0].id}

    assert run(coord.async_sync_season_packs(date(2027, 10, 24))) == ["halloween"]
    assert {c.id for c in coord.storage.get_chores()} == ids  # no duplicates
    assert all(c.enabled for c in coord.storage.get_chores())
    assert coord.storage.get_quests()[0].active
    assert coord.storage.get_quest_child_progress(quest.id, "k1") == {}  # a fresh quest
    assert coord.storage.get_rewards()[0].expires_at == "2027-11-01"
    assert coord.storage.data[SEASON_PACKS_SECTION]["halloween"]["year"] == 2027


def test_switching_off_mid_season_hides_and_on_again_reuses(coord):
    _on(coord, "summer")
    run(coord.async_sync_season_packs(date(2026, 7, 1)))
    assert _counts(coord) == (4, 0, 0, 1, 1)
    coord.storage.set_setting("season_pack_summer", False)
    assert run(coord.async_sync_season_packs(date(2026, 7, 2))) == ["summer"]
    assert not coord.storage.get_challenges()[0].active
    coord.storage.set_setting("season_pack_summer", True)
    assert run(coord.async_sync_season_packs(date(2026, 7, 3))) == ["summer"]
    assert _counts(coord) == (4, 0, 0, 1, 1)
    assert coord.storage.get_challenges()[0].active


def test_a_chore_deleted_mid_season_is_not_made_again(coord):
    _on(coord, "halloween")
    run(coord.async_sync_season_packs(date(2026, 10, 25)))
    victim = next(c for c in coord.storage.get_chores() if c.template_id == "season.halloween.sort_sweets")
    coord.storage.remove_chore(victim.id)
    coord.storage.set_setting("season_pack_halloween", False)
    run(coord.async_sync_season_packs(date(2026, 10, 26)))
    coord.storage.set_setting("season_pack_halloween", True)
    run(coord.async_sync_season_packs(date(2026, 10, 27)))
    run(coord.async_sync_season_packs(date(2027, 10, 25)))
    assert len(coord.storage.get_chores()) == 4
    assert "season.halloween.sort_sweets" not in {c.template_id for c in coord.storage.get_chores()}


def test_chosen_children_and_adults(coord):
    _on(coord, "halloween", season_pack_children={"halloween": ["k2", "a1"]})
    run(coord.async_sync_season_packs(date(2026, 10, 25)))
    assert {tuple(c.assigned_to) for c in coord.storage.get_chores()} == {("k2",)}
    # Changing who it's for re-assigns the live pack.
    coord.storage.set_setting("season_pack_children", {"halloween": []})
    run(coord.async_set_season_pack_children("halloween"))
    assert {tuple(c.assigned_to) for c in coord.storage.get_chores()} == {("k1", "k2")}


def test_back_to_school_waits_for_a_date(coord):
    _on(coord, "back_to_school")
    assert run(coord.async_sync_season_packs(date(2026, 9, 1))) == []
    coord.storage.set_setting("season_school_start", "2026-08-25")
    assert run(coord.async_sync_season_packs(date(2026, 9, 1))) == ["back_to_school"]
    assert len(coord.storage.get_chores()) == 4
    assert coord.storage.get_quests()[0].name == "Ready for School"


def test_easter_eggs_open_one_a_day(coord):
    _on(coord, "easter")
    run(coord.async_sync_season_packs(date(2026, 4, 1)))
    eggs = sorted(coord.storage.get_chores(), key=lambda c: c.created_date)
    assert [c.created_date for c in eggs] == [
        f"2026-0{3 if d < 2 else 4}-{d + 30 if d < 2 else d - 1:02d}" for d in range(7)
    ]
    assert eggs[0].name == "Find hidden egg 1" and eggs[0].schedule_mode == "one_shot"
    # Next year: the same eggs, re-dated to next Easter.
    run(coord.async_sync_season_packs(date(2026, 4, 6)))
    run(coord.async_sync_season_packs(date(2027, 3, 22)))
    assert sorted(c.created_date for c in coord.storage.get_chores())[0] == "2027-03-22"
    assert len(coord.storage.get_chores()) == 7


# ── Advent ───────────────────────────────────────────────────────────────────


def _advent_on(coord, today):
    _on(coord, "christmas")
    run(coord.async_sync_season_packs(today))
    return {int(c.template_id.rsplit("_", 1)[1]): c for c in coord.storage.get_chores() if "advent_" in c.template_id}


def test_advent_door_n_opens_on_day_n(coord):
    doors = _advent_on(coord, date(2026, 12, 1))
    assert len(doors) == 24
    for n, chore in doors.items():
        assert chore.schedule_mode == "one_shot"
        assert chore.created_date == f"2026-12-{n:02d}"
        assert chore.requires_approval
    assert doors[9].name == "Door 9: Write a card for Granny"


def test_advent_availability_per_day(coord):
    doors = _advent_on(coord, date(2026, 12, 1))
    coord.occurrence_override = MagicMock(return_value=None)
    for day, expected in ((1, {1}), (9, {9}), (24, {24}), (25, set())):
        dt_util_mock._now = dt.datetime(2026, 12, day, 9, 0, tzinfo=dt.UTC)
        avail = {n for n, c in doors.items() if coord.is_chore_available_for_child(c, "k1")}
        assert avail == expected


def test_advent_state_letters(coord):
    doors = _advent_on(coord, date(2026, 12, 1))
    when = dt.datetime(2026, 12, 2, 18, 0, tzinfo=dt.UTC)
    coord.storage.add_completion(
        ChoreCompletion(chore_id=doors[1].id, child_id="k1", completed_at=when, approved=True, id="c1")
    )
    coord.storage.add_completion(
        ChoreCompletion(chore_id=doors[3].id, child_id="k1", completed_at=when, approved=False, id="c2")
    )
    dt_util_mock._now = dt.datetime(2026, 12, 4, 9, 0, tzinfo=dt.UTC)
    advent = coord.season_pack_advent(date(2026, 12, 4))
    assert advent["door"] == 4 and advent["chore"] == doors[4].id
    assert advent["goal"] == 20 and advent["badge"] == "Little Elf"
    assert advent["children"]["k1"] == "omp" + "t" + "l" * 20
    assert advent["children"]["k2"] == "mmm" + "t" + "l" * 20
    assert "a1" not in advent["children"]
    # Out of the window, or with the pack off: nothing.
    assert coord.season_pack_advent(date(2026, 12, 27)) is None


def test_little_elf_badge_after_20_doors(coord):
    doors = _advent_on(coord, date(2026, 12, 1))
    dt_util_mock._now = dt.datetime(2026, 12, 21, 9, 0, tzinfo=dt.UTC)
    for n in range(1, 20):
        coord.storage.add_completion(
            ChoreCompletion(
                chore_id=doors[n].id,
                child_id="k1",
                completed_at=dt.datetime(2026, 12, n, 17, 0, tzinfo=dt.UTC),
                approved=True,
                id=f"c{n}",
            )
        )
    run(coord._async_check_season_pack_badges("k1"))
    coord.badges.award_manually.assert_not_awaited()
    coord.storage.add_completion(
        ChoreCompletion(
            chore_id=doors[20].id,
            child_id="k1",
            completed_at=dt.datetime(2026, 12, 20, 17, 0, tzinfo=dt.UTC),
            approved=True,
            id="c20",
        )
    )
    run(coord._async_check_season_pack_badges("k1"))
    badge_id = next(i["id"] for i in _pack_items(coord, "christmas") if i["kind"] == "badge")
    coord.badges.award_manually.assert_awaited_once_with("k1", badge_id, manual=False)


# ── Remove pack ──────────────────────────────────────────────────────────────


def test_remove_pack_uses_recently_deleted_and_switches_off(coord):
    _on(coord, "halloween")
    run(coord.async_sync_season_packs(date(2026, 10, 25)))
    coord._cleanup_chore_from_calendars = AsyncMock()
    coord.remove_chore_from_auctions = MagicMock(return_value=[])
    coord._refund_all_pool_allocations = MagicMock()
    coord.async_refresh.reset_mock()
    removed = run(coord.async_remove_season_pack("halloween"))
    assert removed == 8
    assert _counts(coord) == (0, 0, 0, 0, 0)
    kinds = sorted(e["kind"] for e in coord.recently_deleted())
    assert kinds == ["chore"] * 5 + ["quest", "reward"]
    assert coord.storage.get_setting("season_pack_halloween") is False
    assert "halloween" not in coord.storage.data[SEASON_PACKS_SECTION]
    assert coord.async_refresh.await_count == 1
    # Off, so the next tick doesn't put it back.
    assert run(coord.async_sync_season_packs(date(2026, 10, 26))) == []


def test_remove_pack_never_takes_an_earned_badge(coord):
    from custom_components.taskmate.models import AwardedBadge

    _on(coord, "halloween", "christmas")
    run(coord.async_sync_season_packs(date(2026, 10, 25)))
    badge_id = next(i["id"] for i in _pack_items(coord, "halloween") if i["kind"] == "badge")
    coord.storage.add_awarded_badge(AwardedBadge(child_id="k1", badge_id=badge_id, id="aw1"))
    coord._cleanup_chore_from_calendars = AsyncMock()
    coord.remove_chore_from_auctions = MagicMock(return_value=[])
    coord._refund_all_pool_allocations = MagicMock()
    run(coord.async_remove_season_pack("halloween"))
    kept = coord.storage.get_badge(badge_id)
    assert kept is not None and kept.assigned_to == ["k1"]
    assert coord.storage.has_awarded("k1", badge_id)
    # Still on the child's badges card; not offered to the sibling.
    from custom_components.taskmate.sensor import ChildBadgesSensor

    def attrs(child_id):
        sensor = object.__new__(ChildBadgesSensor)
        sensor.coordinator = coord
        sensor.child_id = child_id
        return sensor.extra_state_attributes

    assert badge_id in {b["badge_id"] for b in attrs("k1")["earned"]}
    k2 = attrs("k2")
    assert badge_id not in {b["badge_id"] for b in k2["earned"] + k2["available"]}
    # The pack's other items are gone, and an unearned badge is removed.
    assert not coord.storage.get_chores() or all("halloween" not in c.template_id for c in coord.storage.get_chores())
    run(coord.async_sync_season_packs(date(2026, 12, 2)))
    xmas_badge = next(i["id"] for i in _pack_items(coord, "christmas") if i["kind"] == "badge")
    run(coord.async_remove_season_pack("christmas"))
    assert coord.storage.get_badge(xmas_badge) is None


def test_remove_pack_command_is_admin_only(coord):
    hass, conn = _ws_env(coord, admin=False)
    msg = {"id": 1, "type": "taskmate/season_packs/remove", "season": "halloween"}
    run(websocket_panel_tools.ws_season_pack_remove(hass, conn, msg))
    conn.send_error.assert_called_once()


# ── Settings ─────────────────────────────────────────────────────────────────

SCHEMA = vol.Schema(ws._UPDATE_SETTINGS_SCHEMA, extra=vol.ALLOW_EXTRA)


def test_settings_accept_the_new_keys():
    out = SCHEMA(
        {
            "type": "taskmate/update_settings",
            "seasonal_easter": True,
            "seasonal_back_to_school": False,
            "season_pack_christmas": True,
            "season_school_start": "2026-08-19",
            "season_pack_children": {"christmas": ["k1", "k1"]},
        }
    )
    assert out["season_pack_children"] == {"christmas": ["k1"]}
    assert SCHEMA({"type": "taskmate/update_settings", "season_school_start": ""})["season_school_start"] == ""
    for key in ("season_pack_christmas", "season_school_start", "season_pack_children", "seasonal_easter"):
        assert key in ws._SUBKEY_SETTINGS


@pytest.mark.parametrize(
    "bad",
    [
        {"season_pack_christmas": "yes"},
        {"season_school_start": "19/08/2026"},
        {"season_school_start": "2026-02-30"},
        {"season_pack_children": {"diwali": ["k1"]}},
        {"season_pack_children": {"christmas": "k1"}},
    ],
)
def test_settings_refuse_bad_values(bad):
    with pytest.raises(vol.Invalid):
        SCHEMA({"type": "taskmate/update_settings", **bad})


def test_saving_settings_installs_a_pack_mid_season(coord):
    hass, conn = _ws_env(coord)
    coord.async_sync_season_packs = AsyncMock(return_value=[])
    coord.async_set_season_pack_children = AsyncMock()
    msg = {
        "id": 1,
        "type": "taskmate/update_settings",
        "season_pack_halloween": True,
        "season_pack_children": {"halloween": ["k1"]},
    }
    run(ws._ws_update_settings(hass, conn, msg))
    coord.async_sync_season_packs.assert_awaited_once_with(refresh=False)
    coord.async_set_season_pack_children.assert_awaited_once_with("halloween")


def test_panel_state_rows(coord):
    _on(coord, "halloween", "back_to_school")
    run(coord.async_sync_season_packs(date(2026, 10, 25)))
    rows = {r["season"]: r for r in coord.season_packs_state(date(2026, 10, 26))}
    assert list(rows) == ["halloween", "christmas", "easter", "back_to_school", "summer"]
    assert rows["halloween"]["state"] == "installed" and rows["halloween"]["installed_on"] == "2026-10-25"
    assert rows["halloween"]["items"] == 8
    assert rows["christmas"]["state"] == "off" and rows["christmas"]["window"] == ["2026-12-01", "2026-12-26"]
    assert rows["back_to_school"]["state"] == "needs_date"
    coord.storage.set_setting("season_pack_christmas", True)
    rows = {r["season"]: r for r in coord.season_packs_state(date(2026, 10, 26))}
    assert rows["christmas"]["state"] == "scheduled"


# ── Sensor ───────────────────────────────────────────────────────────────────


def test_sensor_advent_is_small_and_only_in_season(coord):
    _advent_on(coord, date(2026, 12, 1))
    dt_util_mock._now = dt.datetime(2026, 12, 9, 9, 0, tzinfo=dt.UTC)
    from custom_components.taskmate import sensor as sensor_module

    advent = sensor_module._season_advent(coord)
    assert len(json.dumps(advent)) < 300
    assert set(advent) == {"chore", "door", "goal", "badge", "children"}
    assert len(advent["children"]["k1"]) == 24
    dt_util_mock._now = dt.datetime(2026, 12, 27, 9, 0, tzinfo=dt.UTC)
    assert sensor_module._season_advent(coord) is None
    # A stand-in coordinator (MagicMock) never leaks into the attributes.
    assert sensor_module._season_advent(MagicMock()) is None
    assert sensor_module._season_hidden_ids(MagicMock(), "reward") == set()


def test_overview_carries_advent_without_the_per_child_map():
    from .test_sensor_attributes import _stress_coordinator

    stress = _stress_coordinator()
    stress.season_pack_advent = MagicMock(
        return_value={
            "chore": "c9",
            "door": 9,
            "goal": 20,
            "badge": "Little Elf",
            "children": {"child-0": "o" * 8 + "t" + "l" * 15},
        }
    )
    attrs = TaskMateOverallStatsSensor(stress, MagicMock())._build_attributes()
    assert attrs["advent"] == {"chore": "c9", "door": 9, "goal": 20, "badge": "Little Elf"}
    kids = {c["id"]: c for c in attrs["children"]}
    assert kids["child-0"]["advent"] == "o" * 8 + "t" + "l" * 15
    assert "advent" not in kids["child-1"]
    stress.season_pack_advent = MagicMock(return_value=None)
    attrs = TaskMateOverallStatsSensor(stress, MagicMock())._build_attributes()
    assert "advent" not in attrs
    assert all("advent" not in c for c in attrs["children"])


def test_rewards_of_a_retired_pack_are_hidden_from_cards():
    from custom_components.taskmate import sensor as sensor_module

    from .test_sensor_attributes import _stress_coordinator

    stress = _stress_coordinator()
    stress.season_pack_item_ids = MagicMock(return_value={"reward-00", "reward-01"})
    common = _compute_common(stress)
    ids = {r["id"] for r in sensor_module._build_rewards_list(common, stress)}
    assert "reward-00" not in ids and "reward-02" in ids
    stress.season_pack_item_ids.assert_called_with("reward", state="retired")


def test_badges_sensor_hides_an_unearned_out_of_season_badge(coord):
    from custom_components.taskmate.sensor import ChildBadgesSensor

    _on(coord, "halloween")
    run(coord.async_sync_season_packs(date(2026, 10, 25)))
    run(coord.async_sync_season_packs(date(2026, 11, 1)))
    badge_id = next(i["id"] for i in _pack_items(coord, "halloween") if i["kind"] == "badge")
    sensor = object.__new__(ChildBadgesSensor)
    sensor.coordinator = coord
    sensor.child_id = "k1"
    names = {b["badge_id"] for b in sensor.extra_state_attributes["available"]}
    assert badge_id not in names
    from custom_components.taskmate.models import AwardedBadge

    coord.storage.add_awarded_badge(AwardedBadge(child_id="k1", badge_id=badge_id))
    earned = {b["badge_id"] for b in sensor.extra_state_attributes["earned"]}
    assert badge_id in earned
