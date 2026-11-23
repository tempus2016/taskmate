"""The child's "What did you do?" text outlives the approval (#1283).

The description and suggested points were only visible while a completion
waited for a parent (#1279). They now ride on the chore events, for
automations, and on the activity sensor's ``recent_completions``, for history.
Both are only added when the child actually wrote or suggested something.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from unittest.mock import MagicMock, patch

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.models import Child, Chore, ChoreCompletion

from .test_chore_extras import _setup
from .test_completion_eligibility import _now, run

WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"


def _fired(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


def _submit(**kwargs):
    coord, storage, mod, kid, chore = _setup()
    coord.hass.bus = MagicMock()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        comp = run(coord.async_complete_chore(chore.id, kid.id, **kwargs))
    return coord, storage, mod, comp


# ── the model helper ─────────────────────────────────────────────────────


def test_note_fields_hold_only_what_was_given():
    base = {"chore_id": "ch", "child_id": "k", "completed_at": _now()}
    assert ChoreCompletion(**base).child_note_fields() == {}
    assert ChoreCompletion(**base, note="Swept up").child_note_fields() == {"note": "Swept up"}
    assert ChoreCompletion(**base, suggested_points=5).child_note_fields() == {"suggested_points": 5}
    assert ChoreCompletion(**base, note="Swept up", suggested_points=5).child_note_fields() == {
        "note": "Swept up",
        "suggested_points": 5,
    }


# ── events ───────────────────────────────────────────────────────────────


def test_completed_event_carries_the_description():
    coord, _storage, _mod, _comp = _submit(note="Read two chapters", suggested_points=4)
    (data,) = _fired(coord, "taskmate_chore_completed")
    assert data["note"] == "Read two chapters"
    assert data["suggested_points"] == 4


def test_completed_event_without_a_description_adds_no_keys():
    coord, _storage, _mod, _comp = _submit()
    (data,) = _fired(coord, "taskmate_chore_completed")
    assert "note" not in data and "suggested_points" not in data


def test_approved_event_carries_the_description():
    coord, _storage, mod, comp = _submit(note="Read two chapters", suggested_points=4)
    with patch.object(mod.dt_util, "now", return_value=_now()):
        run(coord.async_approve_chore(comp.id))
    (data,) = _fired(coord, "taskmate_chore_approved")
    assert (data["completion_id"], data["note"], data["suggested_points"]) == (comp.id, "Read two chapters", 4)


def test_approved_event_without_a_description_adds_no_keys():
    coord, _storage, mod, comp = _submit()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        run(coord.async_approve_chore(comp.id))
    (data,) = _fired(coord, "taskmate_chore_approved")
    assert "note" not in data and "suggested_points" not in data


def test_rejected_event_carries_the_description():
    coord, _storage, mod, comp = _submit(note="Read two chapters")
    with patch.object(mod.dt_util, "now", return_value=_now()):
        run(coord.async_reject_chore(comp.id, reason="Only one"))
    (data,) = _fired(coord, "taskmate_chore_rejected")
    assert (data["note"], data["reason"]) == ("Read two chapters", "Only one")
    assert "suggested_points" not in data


def test_auto_approved_event_carries_the_description():
    coord, storage, mod, kid, chore = _setup()
    with patch.object(mod.dt_util, "now", return_value=_now() - dt.timedelta(hours=13)):
        run(coord.async_complete_chore(chore.id, kid.id, note="Read two chapters", suggested_points=4))
    storage.set_setting("auto_approve_hours", 12)
    coord.hass.bus = MagicMock()
    with (
        patch("custom_components.taskmate.coord_auto_approve.dt_util.now", return_value=_now()),
        patch.object(mod.dt_util, "now", return_value=_now()),
    ):
        assert run(coord.async_auto_approve_overdue()) == 1
    (data,) = _fired(coord, "taskmate_chore_auto_approved")
    assert (data["note"], data["suggested_points"]) == ("Read two chapters", 4)


def test_description_is_still_on_the_completion_after_approval():
    coord, storage, mod, comp = _submit(note="Read two chapters", suggested_points=4)
    with patch.object(mod.dt_util, "now", return_value=_now()):
        run(coord.async_approve_chore(comp.id))
    stored = next(c for c in storage.get_completions() if c.id == comp.id)
    assert stored.approved and stored.note == "Read two chapters" and stored.suggested_points == 4


# ── activity sensor history ──────────────────────────────────────────────


def _common(*comps):
    return {
        "child_lookup": {"k1": Child(name="Malia", id="k1")},
        "chore_lookup": {"ch1": Chore(name="Something extra", points=0, id="ch1")},
        "bounty_lookup": {},
        "all_completions": list(comps),
        "chore_undo_seconds": 0,
    }


def test_recent_completions_keep_the_description_after_approval():
    comp = ChoreCompletion(
        chore_id="ch1",
        child_id="k1",
        completed_at=_now(),
        approved=True,
        points_awarded=12,
        note="Raked the drive",
        suggested_points=15,
        id="c1",
    )
    (row,) = sensor_module._build_recent_completions(_common(comp))
    assert (row["note"], row["suggested_points"]) == ("Raked the drive", 15)


def test_recent_completions_without_a_description_add_no_keys():
    comp = ChoreCompletion(chore_id="ch1", child_id="k1", completed_at=_now(), approved=True, id="c1")
    (row,) = sensor_module._build_recent_completions(_common(comp))
    assert "note" not in row and "suggested_points" not in row


def test_recent_completions_with_full_length_notes_stay_under_the_cap():
    comps = [
        ChoreCompletion(
            chore_id="ch1",
            child_id="k1",
            completed_at=_now() - dt.timedelta(minutes=i),
            approved=True,
            note="x" * 200,
            suggested_points=999,
            id=f"c{i}",
        )
        for i in range(50)
    ]
    rows = sensor_module._build_recent_completions(_common(*comps))
    assert len(rows) == 35
    assert len(json.dumps(rows).encode()) < 16384


# ── admin panel ──────────────────────────────────────────────────────────


def test_panel_activity_timeline_shows_the_description():
    src = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")
    assert 'child_note: c.note || ""' in src
    assert "this._childNoteLines({ note: ev.child_note, suggested_points: ev.suggested_points })" in src
