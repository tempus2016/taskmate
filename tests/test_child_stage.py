"""Per-child stage and the Can do / Practising / Later chore marks (#1262)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import voluptuous as vol

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate import websocket as ws
from custom_components.taskmate.const import AGE_GROUPS
from custom_components.taskmate.coord_stages import STAGE_CARD_ITEMS, STAGE_CHORE_ITEMS, STAGE_TIPS
from custom_components.taskmate.models import Child, Chore
from custom_components.taskmate.sensor import _build_children_summary

from .test_setup_wizard import ROOT, _ws_env, coord, run  # noqa: F401  (coord is a fixture)

PANEL = ROOT / "custom_components" / "taskmate" / "www" / "taskmate-panel.js"
CARD = ROOT / "custom_components" / "taskmate" / "www" / "taskmate-child-card.js"


# ── Model ────────────────────────────────────────────────────────────────────


def test_chore_stage_round_trips():
    child = Child(name="Isla", chore_stage={"c1": "practising", "c2": "later"})
    assert Child.from_dict(child.to_dict()).chore_stage == {"c1": "practising", "c2": "later"}


def test_children_saved_before_it_have_no_marks_and_junk_is_dropped():
    assert Child.from_dict({"name": "Old"}).chore_stage == {}
    junk = {"c1": "can", "c2": "maybe", "": "later", "c3": None, "c4": "practising"}
    assert Child.from_dict({"name": "X", "chore_stage": junk}).chore_stage == {"c4": "practising"}
    assert Child.from_dict({"name": "X", "chore_stage": ["c1"]}).chore_stage == {}


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _family(coord, scope="cards"):  # noqa: F811
    coord.storage._data["children"] = [
        Child(name="Isla", id="k1", age_group="6_8").to_dict(),
        Child(name="Vaiha", id="k2").to_dict(),
    ]
    coord.storage._data["chores"] = [
        # Isla's own, with a deadline and deductions.
        Chore(
            name="Brush teeth",
            id="solo",
            assigned_to=["k1"],
            mandatory=True,
            mandatory_penalty_points=3,
            due_time="08:00",
            late_penalty=2,
            early_bonus=1,
        ).to_dict(),
        # Isla's own, nothing to change.
        Chore(name="Shoes on the rack", id="plain", assigned_to=["k1"]).to_dict(),
        # Shared with Vaiha.
        Chore(name="Feed the cat", id="shared", assigned_to=["k1", "k2"], mandatory=True).to_dict(),
        # Everyone (empty assigned_to) counts as shared.
        Chore(name="Tidy up", id="all", assigned_to=[], late_penalty=1, due_time="18:00").to_dict(),
        # Vaiha only: not Isla's at all.
        Chore(name="Mow the lawn", id="other", assigned_to=["k2"], mandatory=True).to_dict(),
    ]
    coord.storage.set_setting("stage_scope", scope)
    coord.async_rearm_mandatory_schedules = AsyncMock()


# ── Plan and apply ───────────────────────────────────────────────────────────


def test_every_stage_has_suggestions():
    for stage in AGE_GROUPS:
        assert STAGE_CARD_ITEMS[stage] and stage in STAGE_CHORE_ITEMS and STAGE_TIPS[stage]


def test_cards_scope_never_touches_chores(coord):  # noqa: F811
    _family(coord, "cards")
    result = run(coord.async_apply_child_stage("k1", "3_5", apply=True))
    assert coord.storage.get_child("k1").age_group == "3_5"
    assert result["chores"] == [] and result["chore_items"] == [] and result["applied"] is False
    assert result["card"] == ["pre_reader_on"]
    solo = coord.storage.get_chore("solo")
    assert solo.mandatory and solo.mandatory_penalty_points == 3 and solo.late_penalty == 2


def test_all_scope_changes_only_the_childs_own_chores_once(coord):  # noqa: F811
    _family(coord, "all")
    preview = coord.stage_plan("k1", "3_5")
    assert [c["chore_id"] for c in preview["chores"]] == ["solo"]
    assert {c["chore_id"] for c in preview["skipped_shared"]} == {"shared", "all"}
    # The preview writes nothing.
    assert coord.storage.get_chore("solo").mandatory is True
    assert coord.storage.get_child("k1").age_group == "6_8"

    result = run(coord.async_apply_child_stage("k1", "3_5", apply=True))
    assert result["applied"] is True
    assert result["chores"] == [
        {
            "chore_id": "solo",
            "name": "Brush teeth",
            "changes": {"mandatory": [True, False], "mandatory_penalty_points": [3, 0], "late_penalty": [2, 0]},
        }
    ]
    solo = coord.storage.get_chore("solo")
    assert (solo.mandatory, solo.mandatory_penalty_points, solo.late_penalty) == (False, 0, 0)
    # Only the deductions go: the due time and its early bonus stay.
    assert solo.due_time == "08:00" and solo.early_bonus == 1
    # Shared and other children's chores are untouched.
    assert coord.storage.get_chore("shared").mandatory is True
    assert coord.storage.get_chore("all").late_penalty == 1
    assert coord.storage.get_chore("other").mandatory is True
    coord.async_rearm_mandatory_schedules.assert_awaited_once()


def test_change_stage_only_leaves_chores_alone(coord):  # noqa: F811
    _family(coord, "all")
    result = run(coord.async_apply_child_stage("k1", "3_5", apply=False))
    assert coord.storage.get_child("k1").age_group == "3_5"
    assert result["chores"] == [] and result["applied"] is False
    assert coord.storage.get_chore("solo").mandatory is True


def test_stages_without_chore_items_change_nothing(coord):  # noqa: F811
    _family(coord, "all")
    for stage in ("6_8", "9_12", "13_plus", ""):
        result = run(coord.async_apply_child_stage("k1", stage, apply=True))
        assert result["chores"] == [] and result["skipped_shared"] == []
    assert coord.storage.get_chore("solo").mandatory is True


# ── WebSocket ────────────────────────────────────────────────────────────────


def test_ws_apply_child_stage_returns_the_diff(coord):  # noqa: F811
    _family(coord, "all")
    hass, conn = _ws_env(coord)
    msg = {"id": 1, "type": "taskmate/apply_child_stage", "child_id": "k1", "stage": "3_5", "preview": True}
    run(ws._ws_apply_child_stage(hass, conn, msg))
    assert conn.send_result.call_args.args[1]["chores"][0]["chore_id"] == "solo"
    assert coord.storage.get_child("k1").age_group == "6_8"
    msg = {"id": 2, "type": "taskmate/apply_child_stage", "child_id": "k1", "stage": "3_5", "apply": True}
    run(ws._ws_apply_child_stage(hass, conn, msg))
    sent = conn.send_result.call_args.args[1]
    assert sent["applied"] is True and [c["chore_id"] for c in sent["skipped_shared"]] == ["shared", "all"]


def test_ws_apply_child_stage_is_admin_only(coord):  # noqa: F811
    _family(coord, "all")
    hass, conn = _ws_env(coord, admin=False)
    msg = {"id": 1, "type": "taskmate/apply_child_stage", "child_id": "k1", "stage": "3_5", "apply": True}
    run(ws._ws_apply_child_stage(hass, conn, msg))
    conn.send_error.assert_called_once()
    assert coord.storage.get_chore("solo").mandatory is True


def test_ws_unknown_child(coord):  # noqa: F811
    _family(coord)
    hass, conn = _ws_env(coord)
    run(ws._ws_apply_child_stage(hass, conn, {"id": 1, "type": "x", "child_id": "nope", "stage": "3_5"}))
    conn.send_error.assert_called_once()


def test_update_child_saves_marks_for_existing_chores_only(coord):  # noqa: F811
    _family(coord)
    hass, conn = _ws_env(coord)
    marks = {"solo": "practising", "plain": "later", "gone": "practising"}
    run(
        ws._ws_update_child(
            hass, conn, {"id": 1, "type": "taskmate/update_child", "child_id": "k1", "chore_stage": marks}
        )
    )
    assert coord.storage.get_child("k1").chore_stage == {"solo": "practising", "plain": "later"}


def test_settings_accept_stage_scope():
    schema = vol.Schema(ws._UPDATE_SETTINGS_SCHEMA)
    assert schema({"type": ws.WS_UPDATE_SETTINGS, "stage_scope": "all"})["stage_scope"] == "all"
    with pytest.raises(vol.Invalid):
        schema({"type": ws.WS_UPDATE_SETTINGS, "stage_scope": "chores"})
    assert "stage_scope" in ws._SUBKEY_SETTINGS


# ── Deleting a chore ─────────────────────────────────────────────────────────


def test_deleting_a_chore_drops_its_marks(coord):  # noqa: F811
    _family(coord)
    child = coord.storage.get_child("k1")
    child.chore_stage = {"solo": "practising", "plain": "later"}
    coord.storage.update_child(child)
    coord.chore_stage_cleanup("solo")
    assert coord.storage.get_child("k1").chore_stage == {"plain": "later"}


def test_remove_chore_runs_the_cleanup():
    src = (ROOT / "custom_components" / "taskmate" / "coord_chores.py").read_text(encoding="utf-8")
    body = src[src.index("async def async_remove_chore") :]
    body = body[: body.index("\n    def ")]
    assert "self.chore_stage_cleanup(chore_id)" in body


# ── Overview sensor ──────────────────────────────────────────────────────────


def test_summary_carries_stage_and_marks_only_when_set():
    from .test_sensor_attributes import _stress_coordinator

    coordinator = _stress_coordinator()
    kids = coordinator.data["children"]
    kids[0].age_group = "3_5"
    kids[0].chore_stage = {"x": "practising"}
    summary = _build_children_summary(coordinator, sensor_module._compute_common(coordinator))
    assert summary[0]["age_group"] == "3_5" and summary[0]["chore_stage"] == {"x": "practising"}
    assert all("chore_stage" not in s and "age_group" not in s for s in summary[1:])


# ── Panel and card wiring ────────────────────────────────────────────────────


def test_panel_mirror_of_the_suggestions_matches():
    src = PANEL.read_text(encoding="utf-8")
    for stage in AGE_GROUPS:
        card = ", ".join(f'"{k}"' for k in STAGE_CARD_ITEMS[stage])
        chores = ", ".join(f'"{k}"' for k in STAGE_CHORE_ITEMS[stage])
        tips = ", ".join(f'"{k}"' for k in STAGE_TIPS[stage])
        assert f'"{stage}": {{ card: [{card}], chores: [{chores}], tips: [{tips}] }}' in src


def test_card_stage_defaults_cover_every_stage():
    src = CARD.read_text(encoding="utf-8")
    for stage in AGE_GROUPS:
        assert f'"{stage}": {{' in src[src.index("const STAGE_CARD_DEFAULTS") :][:600]
