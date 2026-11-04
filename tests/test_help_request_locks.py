"""A help request is refused for a chore the child can't do right now (#771).

The service took "I'm stuck" for a chore whose part of the day hadn't started
or was already over, and for one still in its recurrence window, so parents
got a push about a chore that couldn't be done. It now refuses those with a
translated ServiceValidationError, the same availability the completion path
applies plus the child card's time-of-day rule.
"""

from __future__ import annotations

import json
import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import FakeServiceValidationError
from .test_completion_eligibility import _make_system, _now, run

NOW = "custom_components.taskmate.coord_wellbeing.dt_util.now"
ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
KEYS = ("help_chore_not_open_yet", "help_chore_time_passed", "help_chore_not_available")


def _family(**chore_fields):
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    coord.notifications._has_outstanding_chores_today = lambda _cid: True
    coord.hass.bus = MagicMock()
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Vaiha"))
        chore = run(coord.async_add_chore("Tidy room", points=5, schedule_mode="specific_days"))
    for key, value in chore_fields.items():
        setattr(chore, key, value)
    storage.update_chore(chore)
    return coord, storage, mod, kid, chore


def _ask(coord, mod, kid, chore, hour, minute=0):
    when = _now().replace(hour=hour, minute=minute)
    with patch(NOW, return_value=when), patch.object(mod.dt_util, "now", return_value=when):
        return run(coord.async_request_help(kid.id, chore.id))


def _refused(coord, mod, kid, chore, hour, minute=0):
    with pytest.raises(FakeServiceValidationError) as err:
        _ask(coord, mod, kid, chore, hour, minute)
    coord.notifications.fire.assert_not_called()
    assert err.value.translation_placeholders == {"chore": chore.name}
    return err.value.translation_key


class TestTimeOfDay:
    def test_a_later_part_of_the_day_is_not_open_yet(self):
        coord, _s, mod, kid, chore = _family(time_category="evening")
        assert _refused(coord, mod, kid, chore, 8) == "help_chore_not_open_yet"

    def test_a_part_of_the_day_that_is_over_has_passed(self):
        coord, _s, mod, kid, chore = _family(time_category="morning")
        assert _refused(coord, mod, kid, chore, 20) == "help_chore_time_passed"

    def test_its_own_part_of_the_day_is_fine(self):
        coord, _s, mod, kid, chore = _family(time_category="morning")
        assert _ask(coord, mod, kid, chore, 8)["chore_id"] == chore.id
        coord.notifications.fire.assert_called_once()

    def test_inside_the_claim_allowance_is_fine(self):
        coord, _s, mod, kid, chore = _family(time_category="morning", claim_allowance_minutes=120)
        assert _ask(coord, mod, kid, chore, 13)["chore_id"] == chore.id

    def test_after_the_claim_allowance_has_passed(self):
        coord, _s, mod, kid, chore = _family(time_category="morning", claim_allowance_minutes=60)
        assert _refused(coord, mod, kid, chore, 13, 30) == "help_chore_time_passed"

    def test_before_the_first_period_it_is_still_the_first(self):
        coord, _s, mod, kid, chore = _family(time_category="morning")
        assert _ask(coord, mod, kid, chore, 3)["chore_id"] == chore.id

    def test_anytime_is_always_open(self):
        coord, _s, mod, kid, chore = _family(time_category="anytime")
        for hour in (3, 12, 23):
            _ask(coord, mod, kid, chore, hour)

    def test_follows_the_familys_own_periods(self):
        coord, storage, mod, kid, chore = _family(time_category="school")
        storage.set_setting(
            "time_periods",
            [{"id": "morning", "start": "06:00", "end": "09:00"}, {"id": "school", "start": "09:00", "end": "15:00"}],
        )
        assert _refused(coord, mod, kid, chore, 7) == "help_chore_not_open_yet"
        assert _ask(coord, mod, kid, chore, 10)["chore_id"] == chore.id


class TestAvailability:
    def test_a_recurring_chore_in_its_window_is_refused(self):
        coord, _s, mod, kid, chore = _family(
            schedule_mode="recurring", recurrence="every_3_days", recurrence_start="2024-03-25"
        )
        coord.is_chore_available_for_child = lambda c, cid: False
        assert _refused(coord, mod, kid, chore, 12) == "help_chore_not_available"

    def test_an_available_recurring_chore_is_fine(self):
        coord, _s, mod, kid, chore = _family(schedule_mode="recurring", recurrence="every_3_days")
        coord.is_chore_available_for_child = lambda c, cid: True
        assert _ask(coord, mod, kid, chore, 12)["chore_id"] == chore.id


def test_messages_are_translated_everywhere():
    en = json.loads((ROOT / "strings.json").read_text(encoding="utf-8"))["exceptions"]
    for key in KEYS:
        assert "{chore}" in en[key]["message"]
    for path in sorted((ROOT / "translations").glob("*.json")):
        exc = json.loads(path.read_text(encoding="utf-8"))["exceptions"]
        for key in KEYS:
            assert "{chore}" in exc[key]["message"], f"{path.name} {key}"
            if not path.name.startswith("en"):
                assert exc[key]["message"] != en[key]["message"], f"{path.name} {key} is still English"


def test_help_check_runs_before_anything_is_stored():
    src = (ROOT / "coord_wellbeing.py").read_text(encoding="utf-8")
    body = src[src.index("async def async_request_help") : src.index("def _help_unavailable_reason")]
    assert body.index("_help_unavailable_reason(") < body.index("requests.append(record)")


def test_a_set_time_that_is_not_open_is_refused():
    coord, _s, mod, kid, chore = _family()
    coord.resolve_set_time = lambda *a, **k: None
    with patch("custom_components.taskmate.coord_wellbeing.chore_has_times", return_value=True):
        assert _refused(coord, mod, kid, chore, 12) == "help_chore_not_available"
