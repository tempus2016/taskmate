"""A timed chore can't be started past an unmet prerequisite (#771).

start_timed_task took a dependency-blocked chore, so a session ran on a row
the card then hid (dependency_mode: hide) and the child was paid for a chore
whose prerequisite wasn't done. Completion refuses it; the timed start now
does too, with a translated ServiceValidationError.
"""

from __future__ import annotations

import json
import pathlib
from unittest.mock import patch

import pytest

from custom_components.taskmate.models import ChoreCompletion

from .conftest import FakeServiceValidationError
from .test_completion_eligibility import _make_system, _now, run

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
NOW = "custom_components.taskmate.coord_timed.dt_util.now"


def _setup():
    coord, storage, mod = _make_system()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Vaiha"))
        teeth = run(coord.async_add_chore("Brush teeth", points=1, schedule_mode="specific_days"))
        reading = run(coord.async_add_chore("Reading", points=0, schedule_mode="specific_days"))
    reading.task_type = "timed"
    reading.timed_rate_points = 2
    reading.timed_rate_minutes = 5
    reading.depends_on = [teeth.id]
    storage.update_chore(reading)
    return coord, storage, mod, kid, teeth, reading


def _start(coord, mod, kid, chore):
    with patch.object(mod.dt_util, "now", return_value=_now()), patch(NOW, return_value=_now()):
        run(coord.async_start_timed_task(chore.id, kid.id))


def test_a_blocked_timed_chore_is_refused_with_a_translated_error():
    coord, storage, mod, kid, _teeth, reading = _setup()
    with pytest.raises(FakeServiceValidationError) as err:
        _start(coord, mod, kid, reading)
    assert err.value.translation_key == "timed_start_dependency"
    assert err.value.translation_placeholders == {"chore": "Reading", "chores": "Brush teeth"}
    assert storage.get_timed_sessions() == []


def test_a_pending_prerequisite_still_blocks():
    coord, storage, mod, kid, teeth, reading = _setup()
    storage.add_completion(ChoreCompletion(chore_id=teeth.id, child_id=kid.id, completed_at=_now(), approved=False))
    with pytest.raises(FakeServiceValidationError):
        _start(coord, mod, kid, reading)


def test_once_the_prerequisite_is_approved_it_starts():
    coord, storage, mod, kid, teeth, reading = _setup()
    storage.add_completion(ChoreCompletion(chore_id=teeth.id, child_id=kid.id, completed_at=_now(), approved=True))
    _start(coord, mod, kid, reading)
    assert [s.chore_id for s in storage.get_timed_sessions()] == [reading.id]


def test_availability_and_the_timed_start_share_one_rule():
    coord, storage, mod, kid, teeth, reading = _setup()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        assert coord.unmet_dependencies(reading, kid.id) == [teeth.id]
        assert coord.is_chore_available_for_child(reading, kid.id) is False
    storage.add_completion(ChoreCompletion(chore_id=teeth.id, child_id=kid.id, completed_at=_now(), approved=True))
    with patch.object(mod.dt_util, "now", return_value=_now()):
        assert coord.unmet_dependencies(reading, kid.id) == []


def test_the_message_is_translated_everywhere():
    en = json.loads((ROOT / "strings.json").read_text(encoding="utf-8"))["exceptions"]["timed_start_dependency"][
        "message"
    ]
    assert "{chore}" in en and "{chores}" in en
    for path in sorted((ROOT / "translations").glob("*.json")):
        msg = json.loads(path.read_text(encoding="utf-8"))["exceptions"]["timed_start_dependency"]["message"]
        assert "{chore}" in msg and "{chores}" in msg, path.name
        if not path.name.startswith("en"):
            assert msg != en, f"{path.name} is still English"


def test_polish_message_does_not_put_the_chore_name_in_the_subject():
    """Polish needs the chore in the accusative after "rozpocząć"; a bare
    "{chore} nie można..." read as broken word order. The name now sits in
    quotes after the noun, so it never has to decline."""
    msg = json.loads((ROOT / "translations" / "pl.json").read_text(encoding="utf-8"))["exceptions"][
        "timed_start_dependency"
    ]["message"]
    assert msg.startswith("Nie można jeszcze rozpocząć")
    assert "„{chore}”" in msg
