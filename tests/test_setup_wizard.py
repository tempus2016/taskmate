"""Setup wizard (#980): age groups, the suggestion catalogue and the one-call create."""

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
from custom_components.taskmate.const import AGE_GROUPS, DOMAIN, SCHEDULE_MODES
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child, Chore, Reward
from custom_components.taskmate.setup_catalogue import (
    AGE_GROUP_INFO,
    FREQUENCIES,
    STARTER_REWARDS,
    SUGGESTED_CHORES,
    setup_catalogue,
)
from custom_components.taskmate.storage import TaskMateStorage
from custom_components.taskmate.templates import BUILT_IN_TEMPLATES

ROOT = Path(__file__).resolve().parent.parent
WWW = ROOT / "custom_components" / "taskmate" / "www"
LOCALES = sorted((WWW / "locales").glob("*.json"))
DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
TIME_CATEGORIES = {"morning", "afternoon", "evening", "night", "anytime"}


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Child.age_group ──────────────────────────────────────────────────────────


def test_children_saved_before_the_wizard_have_no_age_group():
    child = Child.from_dict({"name": "Malia", "id": "k1"})
    assert child.age_group == ""
    assert child.to_dict()["age_group"] == ""


def test_age_group_round_trips_and_junk_reads_as_none():
    assert Child.from_dict(Child(name="Vaiha", age_group="6_8").to_dict()).age_group == "6_8"
    for junk in ("7", "adult", None, 9, ["6_8"]):
        assert Child.from_dict({"name": "X", "age_group": junk}).age_group == ""


# ── Catalogue ────────────────────────────────────────────────────────────────


def test_catalogue_age_groups_match_the_model():
    assert tuple(AGE_GROUP_INFO) == AGE_GROUPS
    assert [g["id"] for g in setup_catalogue()["age_groups"]] == list(AGE_GROUPS)


def test_age_groups_are_contiguous():
    prev_max = None
    for gid in AGE_GROUPS:
        info = AGE_GROUP_INFO[gid]
        if prev_max is not None:
            assert info["min_age"] == prev_max + 1
        prev_max = info["max_age"]
    assert prev_max is None  # the oldest group has no upper limit


def test_panel_mirror_of_the_age_groups_matches():
    src = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")
    m = re.search(r"const WZ_AGE_GROUPS = (\[.*?\]);", src)
    assert m
    mirror = json.loads(m.group(1))
    assert [row[0] for row in mirror] == list(AGE_GROUPS)
    for gid, lo, hi in mirror:
        assert lo == AGE_GROUP_INFO[gid]["min_age"]
        assert hi == (AGE_GROUP_INFO[gid]["max_age"] or 999)


def test_every_age_group_has_enough_suggestions():
    for gid in AGE_GROUPS:
        assert len([s for s in SUGGESTED_CHORES if s["age_group"] == gid]) >= 5


def test_suggestion_ids_are_unique_and_translation_safe():
    ids = [s["id"] for s in SUGGESTED_CHORES] + [r["id"] for r in STARTER_REWARDS]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z0-9_]+", i) for i in ids)


def test_suggestions_make_valid_chore_schedules():
    for s in setup_catalogue()["chores"]:
        sched = s["schedule"]
        assert sched["schedule_mode"] in SCHEDULE_MODES
        assert set(sched["due_days"]) <= DAYS
        assert s["time_category"] in TIME_CATEGORIES
        assert s["frequency"] in FREQUENCIES
        assert s["points"] >= 1
        assert s["per_week"] > 0
        assert s["icon"].startswith("mdi:")
        if sched["schedule_mode"] == "recurring":
            assert sched["recurrence"] in ("weekly", "every_2_weeks", "monthly")
            assert sched["recurrence_day"] in DAYS | {""}
        if s["frequency"] == "days":
            assert s["days"] and sched["due_days"] == s["days"]


def test_weekdays_and_daily_schedules():
    by_id = {s["id"]: s for s in setup_catalogue()["chores"]}
    assert by_id["make_bed"]["schedule"] == {"schedule_mode": "specific_days", "due_days": []}
    assert by_id["make_bed"]["per_week"] == 7
    assert len(by_id["pack_school_bag"]["schedule"]["due_days"]) == 5
    assert by_id["mow_lawn"]["schedule"]["recurrence"] == "every_2_weeks"
    assert by_id["mow_lawn"]["schedule"]["recurrence_day"] == "saturday"
    assert by_id["wash_car"]["schedule"]["recurrence_day"] == ""


def test_starter_rewards_have_fixed_positive_costs():
    for r in STARTER_REWARDS:
        assert isinstance(r["cost"], int) and r["cost"] > 0
        assert r["tier"] in setup_catalogue()["reward_tiers"]


@pytest.mark.parametrize("path", LOCALES, ids=lambda p: p.name)
def test_every_suggestion_is_translated_in_every_locale(path):
    strings = json.loads(path.read_text(encoding="utf-8"))
    needed = [f"wizard.chore.{s['id']}" for s in SUGGESTED_CHORES]
    needed += [f"wizard.reward.{r['id']}" for r in STARTER_REWARDS]
    needed += [f"wizard.age_group.{g}" for g in AGE_GROUPS] + [f"wizard.age_group_sub.{g}" for g in AGE_GROUPS]
    needed += [f"wizard.tier.{t}" for t in setup_catalogue()["reward_tiers"]]
    needed += [f"wizard.freq_{f}" for f in FREQUENCIES if f != "days"]
    for tpl in BUILT_IN_TEMPLATES:
        needed.append(f"wizard.pack.{tpl['id']}.name")
        needed += [f"wizard.pack.{tpl['id']}.chore_{i}" for i in range(len(tpl["chores"]))]
    missing = [k for k in needed if not str(strings.get(k, "")).strip()]
    assert not missing, f"{path.name} is missing {missing}"


def test_pack_chore_translations_match_the_english_template():
    en = json.loads((WWW / "locales" / "en.json").read_text(encoding="utf-8"))
    for tpl in BUILT_IN_TEMPLATES:
        assert en[f"wizard.pack.{tpl['id']}.name"] == tpl["name"]
        for i, chore in enumerate(tpl["chores"]):
            assert en[f"wizard.pack.{tpl['id']}.chore_{i}"] == chore["name"]


# ── One-call create ──────────────────────────────────────────────────────────


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


def _chore(name, who, points=2, **extra):
    return {"name": name, "points": points, "assigned_to": who, "schedule_mode": "specific_days", **extra}


def test_creates_children_chores_and_rewards_with_one_refresh(coord):
    result = run(
        coord.async_apply_setup_wizard(
            children=[
                {"ref": "new1", "name": "Malia", "avatar": "mdi:star", "birthday": "2017-05-12", "age_group": "9_12"},
                {"ref": "new2", "name": "Vaiha", "avatar": "mdi:paw", "age_group": "6_8"},
            ],
            chores=[
                _chore("Make bed", ["new2"], icon="mdi:bed-outline", requires_approval=False),
                _chore("Hoover a room", ["new1"], points=4, requires_approval=True, due_days=["saturday"]),
                _chore("Brush teeth", []),
            ],
            rewards=[{"name": "Pick the family film", "cost": 30, "icon": "mdi:movie-open-outline"}],
        )
    )
    kids = {c.name: c for c in coord.storage.get_children()}
    assert kids["Malia"].birthday == "2017-05-12" and kids["Malia"].age_group == "9_12"
    assert kids["Vaiha"].birthday == "" and kids["Vaiha"].age_group == "6_8"
    assert result["children"] == {"new1": kids["Malia"].id, "new2": kids["Vaiha"].id}
    chores = {c.name: c for c in coord.storage.get_chores()}
    assert chores["Make bed"].assigned_to == [kids["Vaiha"].id]
    assert chores["Make bed"].icon == "mdi:bed-outline"
    assert chores["Hoover a room"].requires_approval is True
    assert chores["Hoover a room"].due_days == ["saturday"]
    assert chores["Brush teeth"].assigned_to == []  # template packs go to everyone
    reward = coord.storage.get_rewards()[0]
    assert (reward.name, reward.cost) == ("Pick the family film", 30)
    assert result["chores_added"] == 3 and result["rewards_added"] == 1 and result["children_added"] == 2
    # Bulk-ops rule (#794): one refresh for the whole run.
    coord.async_refresh.assert_awaited_once()


def test_only_adds_never_duplicates(coord):
    existing = Child(name="Malia", age_group="9_12")
    coord.storage.add_child(existing)
    coord.storage.add_chore(Chore(name="Make Bed", points=1))
    coord.storage.add_reward(Reward(name="Friend sleepover", cost=99))
    result = run(
        coord.async_apply_setup_wizard(
            children=[{"ref": "new1", "name": " malia ", "age_group": "3_5"}],
            chores=[_chore("make bed", ["new1"]), _chore("Walk the dog", ["new1"])],
            rewards=[{"name": "FRIEND SLEEPOVER", "cost": 250}, {"name": "Pick the pudding", "cost": 10}],
        )
    )
    assert [c.name for c in coord.storage.get_children()] == ["Malia"]
    assert coord.storage.get_child(existing.id).age_group == "9_12"
    assert result["children"] == {"new1": existing.id}
    assert sorted(c.name for c in coord.storage.get_chores()) == ["Make Bed", "Walk the dog"]
    walk = next(c for c in coord.storage.get_chores() if c.name == "Walk the dog")
    assert walk.assigned_to == [existing.id]
    assert {r.name: r.cost for r in coord.storage.get_rewards()} == {"Friend sleepover": 99, "Pick the pudding": 10}
    assert result["chores_skipped"] == 1 and result["rewards_skipped"] == 1


def test_running_twice_creates_nothing_the_second_time(coord):
    payload = {
        "children": [{"ref": "new1", "name": "Isla", "age_group": "3_5"}],
        "chores": [_chore("Put toys away", ["new1"])],
        "rewards": [{"name": "Pick the pudding", "cost": 10}],
    }
    run(coord.async_apply_setup_wizard(**payload))
    again = run(coord.async_apply_setup_wizard(**payload))
    assert len(coord.storage.get_children()) == 1
    assert len(coord.storage.get_chores()) == 1
    assert len(coord.storage.get_rewards()) == 1
    assert again["children_added"] == again["chores_added"] == again["rewards_added"] == 0


def test_existing_children_only_get_missing_fields_filled_in(coord):
    blank = Child(name="Vaiha")
    set_up = Child(name="Malia", birthday="2017-05-12", age_group="9_12")
    coord.storage.add_child(blank)
    coord.storage.add_child(set_up)
    run(
        coord.async_apply_setup_wizard(
            child_updates=[
                {"child_id": blank.id, "age_group": "6_8"},
                {"child_id": set_up.id, "age_group": "3_5", "birthday": "2020-01-01"},
            ]
        )
    )
    assert coord.storage.get_child(blank.id).age_group == "6_8"
    kept = coord.storage.get_child(set_up.id)
    assert (kept.age_group, kept.birthday) == ("9_12", "2017-05-12")


@pytest.mark.parametrize(
    "bad",
    [
        {"children": [{"ref": "n", "name": "Isla", "birthday": "3000-01-01"}]},
        {"children": [{"ref": "n", "name": "Isla", "birthday": "31/12/2019"}]},
        {"children": [{"ref": "n", "name": "Isla", "age_group": "adults"}]},
        {"children": [{"ref": "n", "name": "Isla"}, {"ref": "n", "name": "Iona"}]},
        {"children": [{"ref": "n", "name": "Isla"}], "chores": [_chore("Walk the dog", ["nobody"])]},
        {"child_updates": [{"child_id": "missing", "age_group": "3_5"}]},
        {"children": [{"ref": "n", "name": "Isla"}], "rewards": [{"name": "  ", "cost": 5}]},
    ],
)
def test_a_bad_item_leaves_the_family_untouched(coord, bad):
    with pytest.raises(ValueError):
        run(coord.async_apply_setup_wizard(**bad))
    assert coord.storage.get_children() == []
    assert coord.storage.get_chores() == []
    assert coord.storage.get_rewards() == []
    coord.async_refresh.assert_not_awaited()


# ── WebSocket commands ───────────────────────────────────────────────────────


def _ws_env(coord, admin=True):
    hass = MagicMock()
    hass.data = {DOMAIN: {"entry": coord}}
    conn = MagicMock()
    conn.user = SimpleNamespace(is_admin=admin, id="u1", name="Parent")
    coord.async_record_audit = AsyncMock()
    return hass, conn


def test_catalogue_command_sends_the_catalogue(coord):
    hass, conn = _ws_env(coord)
    run(websocket_setup.ws_setup_catalogue(hass, conn, {"id": 1, "type": "taskmate/setup_wizard/catalogue"}))
    sent = conn.send_result.call_args.args[1]
    assert [s["id"] for s in sent["chores"]] == [s["id"] for s in SUGGESTED_CHORES]


def test_apply_command_is_admin_only(coord):
    hass, conn = _ws_env(coord, admin=False)
    msg = {"id": 2, "type": "taskmate/setup_wizard/apply", "children": [{"ref": "n", "name": "Isla"}]}
    run(websocket_setup.ws_setup_apply(hass, conn, msg))
    conn.send_error.assert_called_once()
    assert coord.storage.get_children() == []


def test_apply_command_reports_a_bad_payload_as_an_error(coord):
    hass, conn = _ws_env(coord)
    msg = {
        "id": 3,
        "type": "taskmate/setup_wizard/apply",
        "children": [{"ref": "n", "name": "Isla", "birthday": "3000-01-01"}],
    }
    run(websocket_setup.ws_setup_apply(hass, conn, msg))
    assert conn.send_error.call_args.args[1] == "future_birthday"
    assert coord.storage.get_children() == []


@pytest.mark.parametrize(
    ("field", "birthday", "code"),
    [
        ("children", "2019-13-01", "invalid_birthday"),
        ("children", "2019-02-30", "invalid_birthday"),
        ("children", "31/12/2019", "invalid_birthday"),
        ("children", "3000-01-01", "future_birthday"),
        ("child_updates", "2019-13-01", "invalid_birthday"),
    ],
)
def test_apply_command_reports_a_bad_birthday_by_code_not_the_python_error(coord, field, birthday, code):
    coord.storage._data["children"] = [Child(name="Malia", id="k1").to_dict()]
    hass, conn = _ws_env(coord)
    spec = {"ref": "n", "name": "Isla"} if field == "children" else {"child_id": "k1"}
    msg = {"id": 4, "type": "taskmate/setup_wizard/apply", field: [{**spec, "birthday": birthday}]}
    run(websocket_setup.ws_setup_apply(hass, conn, msg))
    conn.send_result.assert_not_called()
    assert conn.send_error.call_args.args[1] == code
    assert "month must be" not in conn.send_error.call_args.args[2]
    assert [c.name for c in coord.storage.get_children()] == ["Malia"]


def test_apply_schemas():
    child = vol.Schema(websocket_setup._CHILD_SCHEMA)
    assert child({"ref": "n", "name": "Isla"})["age_group"] == ""
    with pytest.raises(vol.Invalid):
        child({"ref": "n", "name": "Isla", "age_group": "teen"})
    reward = vol.Schema(websocket_setup._REWARD_SCHEMA)
    with pytest.raises(vol.Invalid):
        reward({"name": "Film", "cost": -1})
    with pytest.raises(vol.Invalid):
        reward({"name": "Film"})  # a fixed cost is required
    chore = vol.Schema(websocket_setup._CHORE_SCHEMA)
    with pytest.raises(vol.Invalid):
        chore({"name": "Film", "schedule_mode": "sometimes"})


def test_setup_commands_are_registered():
    src = (ROOT / "custom_components" / "taskmate" / "websocket.py").read_text(encoding="utf-8")
    assert "SETUP_COMMANDS" in src
    assert websocket_setup.SETUP_COMMANDS == (websocket_setup.ws_setup_catalogue, websocket_setup.ws_setup_apply)


def test_child_commands_accept_an_age_group():
    src = (ROOT / "custom_components" / "taskmate" / "websocket.py").read_text(encoding="utf-8")
    assert src.count('vol.Optional("age_group"') == 2  # add_child + update_child
    assert 'existing.age_group = msg["age_group"]' in src


def test_config_flow_finish_links_to_the_panel():
    for path in [
        ROOT / "custom_components" / "taskmate" / "strings.json",
        *(ROOT / "custom_components" / "taskmate" / "translations").glob("*.json"),
    ]:
        text = json.loads(path.read_text(encoding="utf-8"))["config"]["create_entry"]["default"]
        assert "(/taskmate-admin)" in text, path.name
