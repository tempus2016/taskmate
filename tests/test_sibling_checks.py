"""Sibling checks: an older child checks a younger one's chore."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from custom_components.taskmate import sensor as sensor_module
from custom_components.taskmate.websocket import _UPDATE_SETTINGS_SCHEMA, _validate_sibling_check_pairs

from .test_completion_eligibility import _make_system, _now, run


def _system(bonus=1, pairs=None):
    coord, storage, mod = _make_system()
    coord.notifications = AsyncMock()
    coord.notifications._has_outstanding_chores_today = lambda _cid: True
    coord.hass.bus = MagicMock()
    coord.badges = None
    with patch.object(mod.dt_util, "now", return_value=_now()):
        big = run(coord.async_add_child("Vaiha"))
        small = run(coord.async_add_child("Malia"))
        other = run(coord.async_add_child("Leo"))
        chore = run(coord.async_add_chore("Tidy room", points=5, requires_approval=True))
        run(coord.async_complete_chore(chore.id, small.id))
    storage.set_setting("sibling_check_enabled", True)
    storage.set_setting("sibling_check_bonus", bonus)
    storage.set_setting("sibling_check_pairs", pairs if pairs is not None else {big.id: [small.id]})
    comp = next(c for c in storage.get_completions() if c.child_id == small.id)
    return coord, storage, mod, big, small, other, chore, comp


def _check(coord, mod, checker, comp, verdict, note=""):
    with patch.object(mod.dt_util, "now", return_value=_now()):
        run(coord.async_sibling_check(checker.id, comp.id, verdict, note))


def _fired(coord, name):
    return [c.args[1] for c in coord.hass.bus.async_fire.call_args_list if c.args[0] == name]


class TestQueue:
    def test_checker_sees_the_checkees_waiting_chores(self):
        coord, _storage, mod, big, small, other, chore, comp = _system()
        rows = coord.sibling_checks_for_child(big.id)
        assert [r["completion_id"] for r in rows] == [comp.id]
        assert rows[0]["child_name"] == "Malia" and rows[0]["chore_name"] == "Tidy room"
        assert coord.sibling_checks_for_child(small.id) == []
        assert coord.sibling_checks_for_child(other.id) == []

    def test_nothing_while_off(self):
        coord, storage, _mod, big, *_ = _system()
        storage.set_setting("sibling_check_enabled", False)
        assert coord.sibling_checks_for_child(big.id) == []

    def test_open_ended_chores_are_left_to_parents(self):
        coord, storage, _mod, big, _small, _other, chore, _comp = _system()
        chore.open_ended = True
        storage.update_chore(chore)
        assert coord.sibling_checks_for_child(big.id) == []


class TestLooksDone:
    def test_approves_marks_it_and_pays_the_bonus(self):
        coord, storage, mod, big, small, _other, chore, comp = _system(bonus=2)
        _check(coord, mod, big, comp, "done")
        stored = next(c for c in storage.get_completions() if c.id == comp.id)
        assert stored.approved and stored.checked_by == big.id
        assert storage.get_child(small.id).points == 5
        assert storage.get_child(big.id).points == 2
        txn = storage.get_points_transactions()[-1]
        assert txn.child_id == big.id and txn.reason == "Sibling check: Tidy room"
        (evt,) = _fired(coord, "taskmate_sibling_check")
        assert evt["verdict"] == "done" and evt["bonus"] == 2 and evt["checked_child_id"] == small.id
        (approved,) = _fired(coord, "taskmate_chore_approved")
        assert approved["checked_by"] == big.id
        assert coord.sibling_checks_for_child(big.id) == []

    def test_no_bonus_when_set_to_zero(self):
        coord, storage, mod, big, _small, _other, _chore, comp = _system(bonus=0)
        _check(coord, mod, big, comp, "done")
        assert storage.get_child(big.id).points == 0

    def test_parent_can_still_reject_it(self):
        coord, storage, mod, big, small, _other, _chore, comp = _system()
        _check(coord, mod, big, comp, "done")
        coord._async_notify_rejected = AsyncMock()
        with patch.object(mod.dt_util, "now", return_value=_now()):
            run(coord.async_reject_chore(comp.id))
        assert storage.get_child(small.id).points == 0
        assert not any(c.id == comp.id for c in storage.get_completions())


class TestNotYet:
    def test_leaves_it_waiting_with_the_note(self):
        coord, storage, mod, big, small, _other, _chore, comp = _system()
        _check(coord, mod, big, comp, "not_yet", "  The bed isn't made  ")
        stored = next(c for c in storage.get_completions() if c.id == comp.id)
        assert not stored.approved and stored.checked_by == big.id and stored.check_note == "The bed isn't made"
        assert storage.get_child(big.id).points == 0 and storage.get_child(small.id).points == 0
        assert coord.sibling_checks_for_child(big.id) == []
        feed = coord.recent_sibling_checks()
        assert feed[-1]["verdict"] == "not_yet" and feed[-1]["child_id"] == big.id and feed[-1]["note"]
        # The note reaches the panel through the completion itself.
        assert stored.to_dict()["check_note"] == "The bed isn't made"


class TestRefusals:
    def test_cannot_check_your_own(self):
        coord, _storage, mod, _big, small, _other, _chore, comp = _system()
        with pytest.raises(ValueError, match="own"):
            _check(coord, mod, small, comp, "done")

    def test_must_be_allowed_for_that_child(self):
        coord, _storage, mod, _big, _small, other, _chore, comp = _system()
        with pytest.raises(ValueError, match="can't check"):
            _check(coord, mod, other, comp, "done")

    def test_checked_once_only(self):
        coord, _storage, mod, big, _small, _other, _chore, comp = _system()
        _check(coord, mod, big, comp, "not_yet")
        with pytest.raises(ValueError, match="already"):
            _check(coord, mod, big, comp, "done")

    def test_refused_while_off(self):
        coord, storage, mod, big, _small, _other, _chore, comp = _system()
        storage.set_setting("sibling_check_enabled", False)
        with pytest.raises(ValueError, match="off"):
            _check(coord, mod, big, comp, "done")

    def test_pairs_never_include_yourself(self):
        coord, _storage, _mod, big, small, *_ = _system(pairs={})
        coord.storage.set_setting("sibling_check_pairs", {big.id: [big.id, small.id]})
        assert coord.sibling_checkees(big.id) == [small.id]


class TestSettings:
    def test_pairs_validator_cleans_and_rejects(self):
        assert _validate_sibling_check_pairs({"a": ["b", "b", "a"], "c": []}) == {"a": ["b"]}
        with pytest.raises(vol.Invalid):
            _validate_sibling_check_pairs({"a": "b"})
        keys = {getattr(k, "schema", k) for k in _UPDATE_SETTINGS_SCHEMA}
        assert {"sibling_check_enabled", "sibling_check_pairs", "sibling_check_bonus"} <= keys

    def test_deleting_a_child_drops_them_from_the_pairs(self):
        coord, storage, _mod, big, small, *_ = _system()
        storage.remove_child_from_sections(small.id)
        assert storage.get_setting("sibling_check_pairs") == {big.id: []}


class TestService:
    def test_child_gated_with_the_checker_as_child_id(self):
        from custom_components.taskmate.family_services import async_register_family_services

        hass = MagicMock()
        registered = {}
        hass.services.async_register = lambda d, name, handler, schema=None: registered.setdefault(
            name, (handler, schema)
        )
        coord = MagicMock()
        coord.async_sibling_check = AsyncMock()
        gate = AsyncMock()
        async_register_family_services(
            hass,
            child_action=lambda h: h,
            parent_action=lambda h: h,
            get_coordinator=lambda: coord,
            require_linked_child=gate,
        )
        handler, _schema = registered["sibling_check"]
        call = MagicMock(data={"child_id": "big", "completion_id": "c1", "verdict": "done"})
        run(handler(call))
        gate.assert_awaited_once()
        assert gate.await_args.args[3] == "big"
        coord.async_sibling_check.assert_awaited_once_with("big", "c1", "done", "")


def test_summary_and_overview_carry_the_queue_and_bonus():
    coord, _storage, mod, big, small, _other, _chore, comp = _system(bonus=2)
    with patch.object(mod.dt_util, "now", return_value=_now()):
        coord.data = run(coord._async_update_data())
        common = sensor_module._compute_common(coord)
        summary = {c["id"]: c for c in sensor_module._build_children_summary(coord, common)}
    assert summary[big.id]["sibling_checks"][0]["completion_id"] == comp.id
    assert "sibling_checks" not in summary[small.id]
