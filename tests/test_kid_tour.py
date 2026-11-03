"""Kid onboarding tour: storage, migration, child/parent authorisation, sensor shape.

The tour runs in the cards; the backend keeps one small record per child
(finished on a date, or skipped at step N) so it follows the child across
screens. A child may only mark their own; resetting is a grown-up's job; the
speaker never says words the caller chose.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate import notify_strings
from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate import websocket as ws
from custom_components.taskmate import websocket_tour as wst
from custom_components.taskmate.const import DOMAIN
from custom_components.taskmate.coordinator import TaskMateCoordinator
from custom_components.taskmate.models import Child
from custom_components.taskmate.storage import TaskMateStorage

INTEGRATION = Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
LOCALES = INTEGRATION / "www" / "locales"


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _kids():
    return [
        Child(name="Malia", id="k1", linked_user_id="u_malia"),
        Child(name="Vaiha", id="k2"),
        Child(name="Mum", id="a1", is_adult=True),
    ]


def _coord(settings=None, children=None, tts_entities=("tts.piper",)):
    from tests.conftest import FakeStore

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.entry_id = "test_entry"
    storage._store = FakeStore(None, 1, "test")
    storage._data = {
        "children": [c.to_dict() for c in (children if children is not None else _kids())],
        "chores": [],
        "completions": [],
        "points_name": "Stars",
        "settings": dict(settings or {}),
    }
    storage._data_version = 0

    coord = object.__new__(TaskMateCoordinator)
    coord.hass = MagicMock()
    coord.hass.data = {DOMAIN: {"entry": coord}}
    coord.hass.config.language = "en"
    coord.hass.services.async_call = AsyncMock()
    coord.hass.bus.async_fire = MagicMock()
    coord.hass.states.async_all = MagicMock(return_value=[MagicMock(entity_id=e) for e in tts_entities])
    coord.storage = storage
    coord.async_refresh = AsyncMock()
    return coord


def _wired(settings=None, **users):
    coord = _coord(settings)
    known = {uid: SimpleNamespace(id=uid, is_admin=admin) for uid, admin in users.items()}
    coord.hass.auth.async_get_user = AsyncMock(side_effect=lambda uid: known.get(uid))
    return coord


def _conn(user_id, admin=False):
    connection = MagicMock()
    connection.user = SimpleNamespace(id=user_id, is_admin=admin)
    return connection


def _error_code(connection):
    assert connection.send_error.called, "expected an error"
    return connection.send_error.call_args.args[1]


# ── storage + migration ──────────────────────────────────────────────────────


def _loaded(stored):
    from tests.conftest import FakeStore

    storage = TaskMateStorage.__new__(TaskMateStorage)
    storage.hass = MagicMock()
    storage.entry_id = "e"
    storage._store = FakeStore(None, 1, "t")
    storage._store._data = stored
    storage._data = {}
    storage._data_version = 0
    run(storage.async_load())
    return storage


class TestMigration:
    def test_children_who_already_use_taskmate_are_not_greeted_on_upgrade(self):
        stored = {
            "children": [
                {"id": "old", "name": "Old hand", "total_chores_completed": 12},
                {"id": "pts", "name": "Points only", "total_points_earned": 5},
                {"id": "new", "name": "Newcomer"},
                {"id": "mum", "name": "Mum", "is_adult": True, "total_chores_completed": 3},
            ],
            "chores": [],
        }
        storage = _loaded(stored)
        tour = storage.data["kid_tour"]
        assert tour["old"]["migrated"] is True and tour["old"]["done"]
        assert tour["pts"]["migrated"] is True
        assert "new" not in tour
        assert "mum" not in tour
        assert storage.data["_kid_tour_migrated"] is True

    def test_runs_once_so_a_reset_is_not_undone_on_the_next_restart(self):
        stored = {"children": [{"id": "old", "name": "Old", "total_chores_completed": 4}], "chores": []}
        storage = _loaded(stored)
        storage.data["kid_tour"].pop("old")
        storage._store._data = storage.data
        again = _loaded(storage.data)
        assert "old" not in again.data["kid_tour"]

    def test_a_fresh_install_starts_empty(self):
        storage = _loaded(None)
        assert storage.data["kid_tour"] == {}
        assert storage.data["_kid_tour_migrated"] is True

    def test_deleting_a_child_forgets_their_tour(self):
        coord = _coord()
        run(coord.async_tour_mark("k2", "done"))
        coord.storage.remove_child_from_sections("k2")
        assert coord.tour_state("k2") == {}


# ── coordinator ─────────────────────────────────────────────────────────────


class TestRecord:
    def test_finished_is_stored_with_the_date(self):
        coord = _coord()
        assert coord.tour_done("k1") is False
        record = run(coord.async_tour_mark("k1", "done"))
        assert set(record) == {"done"} and len(record["done"]) == 10
        assert coord.tour_done("k1") is True
        coord.async_refresh.assert_awaited()

    def test_skipped_keeps_the_step_and_clamps_it(self):
        coord = _coord()
        assert run(coord.async_tour_mark("k1", "skipped", 2))["skipped"] == 2
        coord2 = _coord()
        assert run(coord2.async_tour_mark("k1", "skipped", 99))["skipped"] == 5
        assert coord2.tour_done("k1") is True

    def test_the_first_answer_sticks(self):
        coord = _coord()
        run(coord.async_tour_mark("k1", "skipped", 3))
        record = run(coord.async_tour_mark("k1", "done"))
        assert record["skipped"] == 3 and "done" not in record

    def test_reset_forgets_it(self):
        coord = _coord()
        run(coord.async_tour_mark("k1", "done"))
        run(coord.async_tour_reset("k1"))
        assert coord.tour_state("k1") == {} and coord.tour_done("k1") is False

    def test_refuses_grown_ups_unknown_children_and_bad_status(self):
        coord = _coord()
        with pytest.raises(ValueError):
            run(coord.async_tour_mark("a1", "done"))
        with pytest.raises(ValueError, match="not found"):
            run(coord.async_tour_mark("nobody", "done"))
        with pytest.raises(ValueError):
            run(coord.async_tour_mark("k1", "maybe"))

    def test_panel_status_leaves_out_adults_and_children_with_no_record(self):
        coord = _coord()
        run(coord.async_tour_mark("k1", "done"))
        coord.storage.data["kid_tour"]["a1"] = {"done": "2026-01-01"}
        assert set(coord.tour_status_all()) == {"k1"}


class TestSettings:
    def test_on_by_default(self):
        coord = _coord()
        assert coord.tour_enabled() is True and coord.tour_auto_read() is True

    def test_card_settings_absent_while_off(self):
        assert _coord({"tour_enabled": False}).tour_card_settings() is None

    def test_no_speaker_without_a_read_aloud_media_player(self):
        assert _coord().tour_card_settings() == {}

    def test_speaker_and_auto_read_with_one(self):
        coord = _coord({"read_aloud_media_player": "media_player.kitchen"})
        assert coord.tour_card_settings() == {"speak": 1, "auto": 1}
        coord = _coord({"read_aloud_media_player": "media_player.kitchen", "tour_auto_read": False})
        assert coord.tour_card_settings() == {"speak": 1}

    def test_no_speaker_when_no_tts_engine_exists(self):
        coord = _coord({"read_aloud_media_player": "media_player.kitchen"}, tts_entities=())
        assert coord.tour_card_settings() == {}

    def test_settings_are_accepted_and_routed(self):
        assert "tour_enabled" in ws._SUBKEY_SETTINGS and "tour_auto_read" in ws._SUBKEY_SETTINGS
        keys = {getattr(k, "schema", k) for k in ws._UPDATE_SETTINGS_SCHEMA}
        assert {"tour_enabled", "tour_auto_read", "read_aloud_media_player"} <= keys


# ── speech ──────────────────────────────────────────────────────────────────


class TestSpeak:
    def test_words_come_from_the_catalogue_with_name_and_points_name(self):
        coord = _coord()
        coord.storage.data["points_name"] = "Coins"
        msg = coord.build_tour_message("k1", "hello")
        assert msg.startswith("Hi Malia! This is your jobs page")
        assert "Coins" in coord.build_tour_message("k1", "points")

    def test_unknown_step_is_refused(self):
        with pytest.raises(ValueError):
            _coord().build_tour_message("k1", "say_something_rude")

    def test_speaks_through_the_read_aloud_path(self):
        coord = _coord({"read_aloud_media_player": "media_player.kitchen"})
        said = run(coord.async_tour_speak("k1", "tick", "en"))
        call = coord.hass.services.async_call.call_args
        assert call.args[:2] == ("tts", "speak")
        assert call.args[2]["media_player_entity_id"] == "media_player.kitchen"
        assert call.args[2]["message"] == said and said.startswith("Tap here")

    def test_a_hammered_speaker_button_is_throttled(self):
        coord = _coord({"read_aloud_media_player": "media_player.kitchen"})
        run(coord.async_tour_speak("k1", "tick"))
        with pytest.raises(ValueError):
            run(coord.async_tour_speak("k1", "tick"))

    def test_no_speaker_is_an_error_not_silence(self):
        with pytest.raises(ValueError):
            run(_coord().async_tour_speak("k1", "tick"))


# ── WebSocket authorisation ─────────────────────────────────────────────────


def _mark(coord, user, child_id, admin=False, status="done", step=1):
    connection = _conn(user, admin)
    msg = {"id": 1, "type": wst.WS_TOUR_MARK, "child_id": child_id, "status": status, "step": step}
    run(wst.ws_tour_mark(coord.hass, connection, msg))
    return connection


class TestMarkAuth:
    def test_a_child_marks_their_own(self):
        coord = _wired(u_malia=False)
        connection = _mark(coord, "u_malia", "k1")
        connection.send_result.assert_called_once()
        assert coord.tour_done("k1")

    def test_a_child_cannot_mark_a_sibling_linked_to_someone_else(self):
        coord = _wired(u_vaiha=False)
        coord.storage.data["children"][1]["linked_user_id"] = "u_vaiha"
        connection = _mark(coord, "u_vaiha", "k1")
        assert _error_code(connection) == "unauthorized"
        assert not coord.tour_done("k1")

    def test_a_linked_child_cannot_act_through_an_unlinked_one(self):
        coord = _wired(u_malia=False)
        connection = _mark(coord, "u_malia", "k2", status="skipped", step=2)
        assert _error_code(connection) == "unauthorized"
        assert not coord.tour_done("k2")

    def test_an_admin_may_mark_any(self):
        coord = _wired(u_admin=True)
        _mark(coord, "u_admin", "k1", admin=True).send_result.assert_called_once()

    def test_unknown_child(self):
        coord = _wired(u_admin=True)
        assert _error_code(_mark(coord, "u_admin", "zz", admin=True)) == "not_found"


class TestResetAuth:
    def _reset(self, coord, user, admin=False, child_id="k1"):
        connection = _conn(user, admin)
        run(wst.ws_tour_reset(coord.hass, connection, {"id": 2, "type": wst.WS_TOUR_RESET, "child_id": child_id}))
        return connection

    def test_a_parent_resets_any_child(self):
        coord = _wired(u_mum=False)
        coord.storage.set_parent_user_ids(["u_mum"])
        run(coord.async_tour_mark("k1", "done"))
        self._reset(coord, "u_mum").send_result.assert_called_once()
        assert not coord.tour_done("k1")

    def test_a_child_cannot_reset_even_their_own(self):
        coord = _wired(u_malia=False)
        run(coord.async_tour_mark("k1", "done"))
        assert _error_code(self._reset(coord, "u_malia")) == "unauthorized"
        assert coord.tour_done("k1")

    def test_an_admin_resets(self):
        coord = _wired(u_admin=True)
        run(coord.async_tour_mark("k2", "skipped", 1))
        self._reset(coord, "u_admin", admin=True, child_id="k2").send_result.assert_called_once()
        assert coord.tour_state("k2") == {}


class TestSpeakAuth:
    def test_a_child_speaks_only_for_themselves(self):
        coord = _wired({"read_aloud_media_player": "media_player.kitchen"}, u_vaiha=False)
        coord.storage.data["children"][1]["linked_user_id"] = "u_vaiha"
        connection = _conn("u_vaiha")
        msg = {"id": 3, "type": wst.WS_TOUR_SPEAK, "child_id": "k1", "step": "tick", "language": "en"}
        run(wst.ws_tour_speak(coord.hass, connection, msg))
        assert _error_code(connection) == "unauthorized"
        coord.hass.services.async_call.assert_not_called()

    def test_speak_result_is_the_catalogue_text(self):
        coord = _wired({"read_aloud_media_player": "media_player.kitchen"}, u_malia=False)
        connection = _conn("u_malia")
        msg = {"id": 3, "type": wst.WS_TOUR_SPEAK, "child_id": "k1", "step": "hello", "language": "en"}
        run(wst.ws_tour_speak(coord.hass, connection, msg))
        result = connection.send_result.call_args.args[1]
        assert result["message"].startswith("Hi Malia!")

    def test_registered(self):
        assert {wst.ws_tour_mark, wst.ws_tour_speak, wst.ws_tour_reset} <= set(wst.TOUR_COMMANDS)


# ── sensor shape ────────────────────────────────────────────────────────────


def _summary(coord):
    from custom_components.taskmate import coordinator as coord_mod

    from .test_completion_eligibility import _now

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(coord_mod.dt_util, "now", lambda: _now())
        mp.setattr(sensor_module.dt_util, "now", lambda: _now())
        coord.data = run(coord._async_update_data())
        common = sensor_module._compute_common(coord)
        return {c["id"]: c for c in sensor_module._build_children_summary(coord, common)}


class TestSensor:
    def _system(self, settings=None):
        from .test_completion_eligibility import _make_system, _now

        coord, storage, mod = _make_system()
        coord.hass.states.async_all = MagicMock(return_value=[])
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(mod.dt_util, "now", lambda: _now())
            kid = run(coord.async_add_child("Malia"))
            grown = run(coord.async_add_child("Dad", is_adult=True))
        for k, v in (settings or {}).items():
            storage.set_setting(k, v)
        return coord, kid, grown

    def test_one_boolean_per_child_while_on(self):
        coord, kid, grown = self._system()
        summary = _summary(coord)
        assert summary[kid.id]["tour_done"] is False
        assert "tour_done" not in summary[grown.id]
        run(coord.async_tour_mark(kid.id, "done"))
        assert _summary(coord)[kid.id]["tour_done"] is True

    def test_absent_while_off(self):
        coord, kid, _grown = self._system({"tour_enabled": False})
        assert "tour_done" not in _summary(coord)[kid.id]


# ── plumbing ────────────────────────────────────────────────────────────────


def test_the_tour_module_loads_before_the_cards_that_use_it():
    src = (INTEGRATION / "frontend.py").read_text(encoding="utf-8")
    cards = src[src.index("CARDS: Final = [") : src.index("RETIRED_CARDS")]
    assert cards.index('"taskmate-tour.js"') < cards.index('"taskmate-child-card.js"')
    assert cards.index('"taskmate-tour.js"') < cards.index('"taskmate-kiosk-card.js"')


def test_every_speakable_step_has_title_and_body_in_english_and_every_locale():
    from custom_components.taskmate.coord_tour import TOUR_SPEAKABLE

    for step in TOUR_SPEAKABLE:
        assert notify_strings.DEFAULTS.get(f"tour_{step}_title")
        assert notify_strings.DEFAULTS.get(f"tour_{step}_body")
    for path in LOCALES.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for step in TOUR_SPEAKABLE:
            assert data.get(f"notify.tour_{step}_title"), f"{path.name} {step}"
