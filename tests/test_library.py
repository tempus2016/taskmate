"""📚 Library: the catalogue, template ids, the one-call add and the packs."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol

from custom_components.taskmate import websocket_setup
from custom_components.taskmate.const import DOMAIN, SCHEDULE_MODES
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Chore, Reward, clean_template_id
from custom_components.taskmate.setup_catalogue import (
    CHORE_CATEGORIES,
    FREQUENCIES,
    LIBRARY_CHORES,
    LIBRARY_REWARDS,
    REWARD_TIERS,
    STARTER_REWARDS,
    SUGGESTED_CHORES,
    library_catalogue,
    setup_catalogue,
)
from custom_components.taskmate.storage import TaskMateStorage
from custom_components.taskmate.templates import BUILT_IN_TEMPLATES

ROOT = Path(__file__).resolve().parent.parent
WWW = ROOT / "custom_components" / "taskmate" / "www"
LOCALES = sorted((WWW / "locales").glob("*.json"))
PANEL = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")
DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
TIME_CATEGORIES = {"morning", "afternoon", "evening", "night", "anytime"}


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Catalogue ────────────────────────────────────────────────────────────────


def test_about_two_hundred_chores_and_forty_five_rewards():
    assert 190 <= len(LIBRARY_CHORES) <= 220
    assert 40 <= len(LIBRARY_REWARDS) <= 50


def test_ids_are_unique_and_translation_safe():
    ids = [c["id"] for c in LIBRARY_CHORES] + [r["id"] for r in LIBRARY_REWARDS]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z0-9_]+", i) for i in ids)
    # Every id is also a valid template id, so "already added" can find it.
    assert all(clean_template_id(i) == i for i in ids)


def test_the_wizard_suggestions_are_the_top_picks_unchanged():
    tops = [c for c in LIBRARY_CHORES if c["top_pick"]]
    assert [c["id"] for c in tops] == [s["id"] for s in SUGGESTED_CHORES]
    for lib, s in zip(tops, SUGGESTED_CHORES, strict=True):
        assert (lib["points"], lib["frequency"], lib["days"], lib["time_category"], lib["icon"]) == (
            s["points"],
            s["frequency"],
            s["days"],
            s["time_category"],
            s["icon"],
        )
    assert [r["id"] for r in LIBRARY_REWARDS if r["top_pick"]] == [r["id"] for r in STARTER_REWARDS]
    # The wizard's own lists are untouched.
    assert len(setup_catalogue()["chores"]) == len(SUGGESTED_CHORES) == 32


def test_every_category_is_used_and_well_stocked():
    assert len(CHORE_CATEGORIES) == 12
    for cat in CHORE_CATEGORIES:
        assert len([c for c in LIBRARY_CHORES if c["category"] == cat]) >= 8, cat
    assert {c["category"] for c in LIBRARY_CHORES} == set(CHORE_CATEGORIES)


def test_ages_are_sane():
    for c in LIBRARY_CHORES:
        assert 3 <= c["min_age"] <= 14, c["id"]
        assert c["max_age"] is None or c["min_age"] <= c["max_age"] <= 17, c["id"]
    for r in LIBRARY_REWARDS:
        assert 3 <= r["min_age"] <= 14, r["id"]


def test_there_is_something_for_every_age():
    def suits(c, age):
        return c["min_age"] <= age <= (c["max_age"] if c["max_age"] is not None else 99)

    for age in range(3, 18):
        assert len([c for c in LIBRARY_CHORES if suits(c, age)]) >= 25, age


def test_library_chores_make_valid_schedules():
    for c in library_catalogue()["chores"]:
        sched = c["schedule"]
        assert sched["schedule_mode"] in SCHEDULE_MODES
        assert set(sched["due_days"]) <= DAYS
        assert c["time_category"] in TIME_CATEGORIES
        assert c["frequency"] in FREQUENCIES
        assert c["points"] >= 1 and isinstance(c["points"], int)
        assert c["per_week"] > 0
        assert c["icon"].startswith("mdi:")
        if c["frequency"] == "days":
            assert c["days"] and sched["due_days"] == c["days"]


def test_library_rewards_have_fixed_positive_costs():
    for r in LIBRARY_REWARDS:
        assert isinstance(r["cost"], int) and r["cost"] > 0, r["id"]
        assert r["tier"] in REWARD_TIERS
        assert r["icon"].startswith("mdi:")
    for tier in REWARD_TIERS:
        assert len([r for r in LIBRARY_REWARDS if r["tier"] == tier]) >= 8


def test_catalogue_serves_the_library():
    lib = setup_catalogue()["library"]
    assert lib["categories"] == list(CHORE_CATEGORIES)
    assert [c["id"] for c in lib["chores"]] == [c["id"] for c in LIBRARY_CHORES]
    assert [r["id"] for r in lib["rewards"]] == [r["id"] for r in LIBRARY_REWARDS]


def test_packs_are_the_built_in_templates():
    packs = library_catalogue()["packs"]
    assert [p["id"] for p in packs] == [t["id"] for t in BUILT_IN_TEMPLATES]
    for pack, tpl in zip(packs, BUILT_IN_TEMPLATES, strict=True):
        assert pack["name"] == tpl["name"]
        assert [c["name"] for c in pack["chores"]] == [c["name"] for c in tpl["chores"]]
        # Their template ids (pack.<id>.<n>) are valid too.
        assert all(clean_template_id(f"pack.{pack['id']}.{i}") for i in range(len(pack["chores"])))


# ── Names ────────────────────────────────────────────────────────────────────


def _panel_library_keys() -> set[str]:
    return set(re.findall(r'"(library\.[a-z_]+)"', PANEL)) | {f"library.tab_{k}" for k in ("chores", "rewards")}


@pytest.mark.parametrize("path", LOCALES, ids=lambda p: p.name)
def test_every_library_entry_and_string_is_translated(path):
    strings = json.loads(path.read_text(encoding="utf-8"))
    needed = [f"wizard.chore.{c['id']}" for c in LIBRARY_CHORES]
    needed += [f"wizard.reward.{r['id']}" for r in LIBRARY_REWARDS]
    needed += [f"wizard.cat.{c}" for c in CHORE_CATEGORIES]
    needed += sorted(_panel_library_keys())
    missing = [k for k in needed if not str(strings.get(k, "")).strip()]
    assert not missing, f"{path.name} is missing {missing}"


def test_the_panel_uses_library_strings():
    # The scan above would pass vacuously if the panel used none.
    assert len(_panel_library_keys()) >= 30


@pytest.mark.parametrize("path", [p for p in LOCALES if p.stem not in ("en", "en-GB")], ids=lambda p: p.name)
def test_library_names_are_really_translated(path):
    en = json.loads((WWW / "locales" / "en.json").read_text(encoding="utf-8"))
    strings = json.loads(path.read_text(encoding="utf-8"))
    keys = [f"wizard.chore.{c['id']}" for c in LIBRARY_CHORES] + [f"wizard.reward.{r['id']}" for r in LIBRARY_REWARDS]
    same = [k for k in keys if strings[k] == en[k]]
    # A few names are the same word in both languages ("Fotoprojekt"); an
    # English copy left in place would show up as many more.
    assert len(same) <= len(keys) * 0.05, same


@pytest.mark.parametrize("path", LOCALES, ids=lambda p: p.name)
def test_placeholders_match_english(path):
    en = json.loads((WWW / "locales" / "en.json").read_text(encoding="utf-8"))
    strings = json.loads(path.read_text(encoding="utf-8"))
    for k in _panel_library_keys():
        assert set(re.findall(r"\{(\w+)\}", strings[k])) == set(re.findall(r"\{(\w+)\}", en[k])), k


# ── template_id ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "clean"),
    [
        ("make_bed", "make_bed"),
        ("pack.pet_care.2", "pack.pet_care.2"),
        ("", ""),
        (None, ""),
        ("Make Bed", ""),
        ("<script>", ""),
        ("a" * 81, ""),
        (42, "42"),
    ],
)
def test_clean_template_id(raw, clean):
    assert clean_template_id(raw) == clean


def test_template_id_round_trips_on_chores_and_rewards():
    chore = Chore.from_dict(Chore(name="Make bed", template_id="make_bed").to_dict())
    assert chore.template_id == "make_bed"
    reward = Reward.from_dict(Reward(name="Sleepover", template_id="sleepover").to_dict())
    assert reward.template_id == "sleepover"
    # Records saved before the field existed read as "made by hand".
    legacy = Chore(name="Old").to_dict()
    del legacy["template_id"]
    assert Chore.from_dict(legacy).template_id == ""
    assert Chore.from_dict({**legacy, "template_id": "<b>x</b>"}).template_id == ""


@pytest.fixture
def coord():
    hass = MagicMock()
    storage = TaskMateStorage(hass, "test_entry")
    storage._store = MagicMock()
    storage._store.async_load = AsyncMock(return_value=None)
    storage._store.async_save = AsyncMock()
    storage._store.async_delay_save = MagicMock()
    run(storage.async_load())
    c = object.__new__(TaskMateCoordinator)
    c.storage = storage
    c.async_refresh = AsyncMock()
    c.async_check_birthdays = AsyncMock(return_value=[])
    return c


def test_template_id_survives_a_backup_and_restore(coord):
    coord.storage.add_chore(Chore(name="Make bed", template_id="make_bed"))
    coord.storage.add_reward(Reward(name="Sleepover", cost=250, template_id="sleepover"))
    backup = json.loads(json.dumps(coord.export_config()))
    coord.storage.import_data({"children": [], "chores": [], "rewards": []})
    assert coord.storage.get_chores() == []
    run(coord.async_import_config(backup))
    assert [c.template_id for c in coord.storage.get_chores()] == ["make_bed"]
    assert [r.template_id for r in coord.storage.get_rewards()] == ["sleepover"]


# ── Adding in one go ─────────────────────────────────────────────────────────


def _chore(name, who, tpl="", points=2, **extra):
    spec = {"name": name, "points": points, "assigned_to": who, "schedule_mode": "specific_days", **extra}
    if tpl:
        spec["template_id"] = tpl
    return spec


def test_library_add_keeps_the_template_ids_with_one_refresh(coord):
    from custom_components.taskmate.models import Child

    kid = Child(name="Isla")
    coord.storage.add_child(kid)
    result = run(
        coord.async_apply_setup_wizard(
            chores=[_chore("Make bed", [kid.id], "make_bed"), _chore("Feed pet", [], "pack.pet_care.0")],
            rewards=[{"name": "Sleepover", "cost": 250, "icon": "mdi:sleep", "template_id": "sleepover"}],
        )
    )
    chores = {c.name: c for c in coord.storage.get_chores()}
    assert chores["Make bed"].template_id == "make_bed"
    assert chores["Make bed"].assigned_to == [kid.id]
    assert chores["Feed pet"].template_id == "pack.pet_care.0"
    assert coord.storage.get_rewards()[0].template_id == "sleepover"
    assert result["chores_added"] == 2 and result["rewards_added"] == 1
    # Bulk-ops rule (#794): one refresh for the whole batch.
    coord.async_refresh.assert_awaited_once()


@pytest.mark.parametrize(("bank_on", "minutes"), [(True, 15), (False, 0)])
def test_library_screen_time_reward_fills_the_bank_only_while_it_is_on(coord, bank_on, minutes):
    coord.storage.set_setting("screen_time_enabled", bank_on)
    run(
        coord.async_apply_setup_wizard(
            rewards=[
                {"name": "15 min extra screen time", "cost": 15, "template_id": "screen_time"},
                {"name": "Sleepover", "cost": 250, "template_id": "sleepover"},
            ],
        )
    )
    rewards = {r.template_id: r for r in coord.storage.get_rewards()}
    assert rewards["screen_time"].screen_minutes == minutes
    assert rewards["sleepover"].screen_minutes == 0


def test_already_added_by_template_even_after_a_rename(coord):
    coord.storage.add_chore(Chore(name="Bed!", template_id="make_bed"))
    coord.storage.add_reward(Reward(name="Big sleepover", cost=300, template_id="sleepover"))
    result = run(
        coord.async_apply_setup_wizard(
            chores=[_chore("Make bed", [], "make_bed"), _chore("Hoover a room", [], "hoover_room")],
            rewards=[{"name": "Friend sleepover", "cost": 250, "template_id": "sleepover"}],
        )
    )
    assert sorted(c.name for c in coord.storage.get_chores()) == ["Bed!", "Hoover a room"]
    assert [r.name for r in coord.storage.get_rewards()] == ["Big sleepover"]
    assert result["chores_skipped"] == 1 and result["rewards_skipped"] == 1


def test_already_added_by_name_when_made_by_hand(coord):
    coord.storage.add_chore(Chore(name="Make Bed"))
    result = run(coord.async_apply_setup_wizard(chores=[_chore("make bed", [], "make_bed")]))
    assert [c.name for c in coord.storage.get_chores()] == ["Make Bed"]
    assert result["chores_skipped"] == 1


def test_the_same_chore_twice_in_one_batch_is_added_once(coord):
    result = run(
        coord.async_apply_setup_wizard(
            chores=[
                _chore("Brush teeth", [], "pack.morning_routine.1"),
                _chore("brush teeth", [], "pack.evening_routine.0"),
            ]
        )
    )
    assert [c.name for c in coord.storage.get_chores()] == ["Brush teeth"]
    assert result["chores_added"] == 1 and result["chores_skipped"] == 1


def _ws_env(coord, admin=True):
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry": coord}}
    conn = MagicMock()
    conn.user = SimpleNamespace(is_admin=admin, id="u1", name="Parent")
    coord.async_record_audit = AsyncMock()
    return hass, conn


def test_library_add_command_adds_and_reports(coord):
    hass, conn = _ws_env(coord)
    msg = {
        "id": 1,
        "type": "taskmate/library/add",
        "chores": [_chore("Make bed", [], "make_bed")],
        "rewards": [{"name": "Sleepover", "cost": 250, "template_id": "sleepover"}],
    }
    run(websocket_setup.ws_library_add(hass, conn, msg))
    sent = conn.send_result.call_args.args[1]
    assert sent["chores_added"] == 1 and sent["rewards_added"] == 1
    # Logged as a library add, not as the wizard.
    assert coord.async_record_audit.await_args.args[2] == "library/add"


def test_library_add_command_is_admin_only(coord):
    hass, conn = _ws_env(coord, admin=False)
    msg = {"id": 2, "type": "taskmate/library/add", "chores": [_chore("Make bed", [], "make_bed")]}
    run(websocket_setup.ws_library_add(hass, conn, msg))
    conn.send_error.assert_called_once()
    assert coord.storage.get_chores() == []


def test_library_add_rejects_an_unknown_child(coord):
    hass, conn = _ws_env(coord)
    msg = {"id": 3, "type": "taskmate/library/add", "chores": [_chore("Make bed", ["nobody"], "make_bed")]}
    run(websocket_setup.ws_library_add(hass, conn, msg))
    conn.send_error.assert_called_once()
    assert coord.storage.get_chores() == []


def test_schemas_take_a_template_id():
    chore = vol.Schema(websocket_setup._CHORE_SCHEMA)
    assert chore({"name": "Make bed", "template_id": "make_bed"})["template_id"] == "make_bed"
    with pytest.raises(vol.Invalid):
        chore({"name": "Make bed", "template_id": "x" * 81})
    reward = vol.Schema(websocket_setup._REWARD_SCHEMA)
    assert reward({"name": "Film", "cost": 5, "template_id": "family_film"})["template_id"] == "family_film"
