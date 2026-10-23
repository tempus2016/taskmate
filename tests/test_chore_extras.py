"""Estimated minutes, reference photos, quantity chores and the auto-approve timeout."""

from __future__ import annotations

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.taskmate.models import Chore, ChoreCompletion

from .test_completion_eligibility import _make_system, _now, run


def _setup(**chore_fields):
    coord, storage, mod = _make_system()
    notifications = AsyncMock()
    notifications._has_outstanding_chores_today = lambda _cid: True
    coord.notifications = notifications
    with patch.object(mod.dt_util, "now", return_value=_now()):
        kid = run(coord.async_add_child("Vaiha"))
        chore = run(coord.async_add_chore("Read", points=2, requires_approval=True, schedule_mode="specific_days"))
        for key, value in chore_fields.items():
            setattr(chore, key, value)
        storage.update_chore(chore)
    return coord, storage, mod, kid, chore


class TestModel:
    def test_new_chore_fields_round_trip(self):
        chore = Chore(
            name="Read",
            estimated_minutes=25,
            reference_image_url="/api/taskmate/image/abc.jpg",
            quantity_unit="pages",
            quantity_max=50,
        )
        again = Chore.from_dict(chore.to_dict())
        assert (again.estimated_minutes, again.reference_image_url, again.quantity_unit, again.quantity_max) == (
            25,
            "/api/taskmate/image/abc.jpg",
            "pages",
            50,
        )

    def test_old_chores_load_with_defaults_and_bad_values_are_clamped(self):
        assert Chore.from_dict({"name": "Old"}).estimated_minutes == 0
        assert Chore.from_dict({"name": "Odd", "estimated_minutes": "x", "quantity_max": -4}).quantity_max == 0
        assert Chore.from_dict({"name": "Huge", "estimated_minutes": 99999}).estimated_minutes == 600

    def test_completion_quantity_and_auto_flag_only_stored_when_set(self):
        plain = ChoreCompletion(chore_id="c", child_id="k", completed_at=_now()).to_dict()
        assert "quantity" not in plain and "auto_approved" not in plain
        rich = ChoreCompletion(chore_id="c", child_id="k", completed_at=_now(), quantity=12, auto_approved=True)
        again = ChoreCompletion.from_dict(rich.to_dict())
        assert again.quantity == 12 and again.auto_approved is True


class TestQuantityChores:
    def test_child_must_say_how_many(self):
        coord, _storage, mod, kid, chore = _setup(quantity_unit="pages")
        with patch.object(mod.dt_util, "now", return_value=_now()), pytest.raises(ValueError, match="pages"):
            run(coord.async_complete_chore(chore.id, kid.id))

    def test_points_are_per_unit(self):
        coord, _storage, mod, kid, chore = _setup(quantity_unit="pages")
        with patch.object(mod.dt_util, "now", return_value=_now()):
            comp = run(coord.async_complete_chore(chore.id, kid.id, quantity=12))
        assert comp.quantity == 12
        assert comp.submitted_points == 24

    def test_cap_applies(self):
        coord, _storage, mod, kid, chore = _setup(quantity_unit="pages", quantity_max=10)
        with patch.object(mod.dt_util, "now", return_value=_now()):
            comp = run(coord.async_complete_chore(chore.id, kid.id, quantity=40))
        assert comp.quantity == 10
        assert comp.submitted_points == 20

    def test_uncapped_quantity_always_goes_to_a_parent(self):
        coord, _storage, mod, kid, chore = _setup(quantity_unit="pages", requires_approval=False)
        with patch.object(mod.dt_util, "now", return_value=_now()):
            comp = run(coord.async_complete_chore(chore.id, kid.id, quantity=10000))
        assert comp.approved is False

    def test_capped_quantity_can_self_approve(self):
        coord, storage, mod, kid, chore = _setup(quantity_unit="pages", quantity_max=10, requires_approval=False)
        with patch.object(mod.dt_util, "now", return_value=_now()):
            comp = run(coord.async_complete_chore(chore.id, kid.id, quantity=4))
        assert comp.approved is True
        assert storage.get_child(kid.id).points == 8

    def test_parent_ticking_without_a_number_counts_one(self):
        coord, storage, mod, kid, chore = _setup(quantity_unit="laps")
        with patch.object(mod.dt_util, "now", return_value=_now()):
            comp = run(coord.async_complete_chore(chore.id, kid.id, as_parent=True))
        assert comp.quantity == 1
        assert storage.get_child(kid.id).points == 2

    def test_approval_pays_what_was_submitted(self):
        coord, storage, mod, kid, chore = _setup(quantity_unit="pages")
        with patch.object(mod.dt_util, "now", return_value=_now()):
            comp = run(coord.async_complete_chore(chore.id, kid.id, quantity=7))
            run(coord.async_approve_chore(comp.id))
        assert storage.get_child(kid.id).points == 14

    def test_ignored_on_an_ordinary_chore(self):
        coord, _storage, mod, kid, chore = _setup()
        with patch.object(mod.dt_util, "now", return_value=_now()):
            comp = run(coord.async_complete_chore(chore.id, kid.id, quantity=9))
        assert comp.quantity == 0
        assert comp.submitted_points == 2

    def test_watch_skips_quantity_chores(self):
        from custom_components.taskmate.watch import chore_needs_input

        coord, _storage, _mod, _kid, chore = _setup(quantity_unit="pages")
        assert chore_needs_input(coord, chore) is True


class TestReferenceImage:
    def test_replacing_or_clearing_deletes_the_old_file(self):
        coord, storage, mod, _kid, chore = _setup(reference_image_url="/api/taskmate/image/old.jpg")
        deleted = []
        with (
            patch.object(mod.dt_util, "now", return_value=_now()),
            patch(
                "custom_components.taskmate.coord_chores.images.async_delete_image",
                AsyncMock(side_effect=lambda h, u: deleted.append(u)),
            ),
        ):
            chore.reference_image_url = "/api/taskmate/image/new.jpg"
            run(coord.async_update_chore(chore))
            assert deleted == ["/api/taskmate/image/old.jpg"]
            run(coord.async_remove_chore(chore.id))
            # Kept while the chore can still be restored from Recently deleted...
            assert deleted == ["/api/taskmate/image/old.jpg"]
        # ...and deleted with the snapshot after 7 days.
        with (
            patch("custom_components.taskmate.coord_trash.dt_util.now", return_value=_now() + dt.timedelta(days=8)),
            patch(
                "custom_components.taskmate.coord_chores.images.async_delete_image",
                AsyncMock(side_effect=lambda h, u: deleted.append(u)),
            ),
        ):
            run(coord.async_purge_recently_deleted())
        assert deleted == ["/api/taskmate/image/old.jpg", "/api/taskmate/image/new.jpg"]

    def test_a_picture_another_chore_uses_is_kept(self):
        coord, storage, mod, _kid, chore = _setup(reference_image_url="/api/taskmate/image/shared.jpg")
        with patch.object(mod.dt_util, "now", return_value=_now()):
            other = run(coord.async_add_chore("Other", points=1))
        other.image_url = "/api/taskmate/image/shared.jpg"
        storage.update_chore(other)
        deleted = []
        with (
            patch.object(mod.dt_util, "now", return_value=_now()),
            patch(
                "custom_components.taskmate.coord_chores.images.async_delete_image",
                AsyncMock(side_effect=lambda h, u: deleted.append(u)),
            ),
        ):
            run(coord.async_remove_chore(chore.id))
        assert deleted == []


class TestEstimatedMinutesInFairness:
    def test_minutes_are_totalled_per_child(self):
        coord, storage, mod, kid, chore = _setup(estimated_minutes=15, requires_approval=False)
        with patch.object(mod.dt_util, "now", return_value=_now()):
            run(coord.async_complete_chore(chore.id, kid.id))
            report = coord.fairness_report(7)
        row = report["children"][0]
        assert row["minutes"] == 15
        assert report["total_minutes"] == 15
        assert row["share_minutes"] == 100.0


class TestAutoApprove:
    def _pending(self, hours_ago, **fields):
        coord, storage, mod, kid, chore = _setup(**fields)
        with patch.object(mod.dt_util, "now", return_value=_now() - dt.timedelta(hours=hours_ago)):
            comp = run(
                coord.async_complete_chore(chore.id, kid.id, **({"note": "x"} if fields.get("open_ended") else {}))
            )
        return coord, storage, mod, kid, comp

    def test_off_by_default(self):
        coord, storage, mod, _kid, comp = self._pending(48)
        with patch.object(mod.dt_util, "now", return_value=_now()):
            assert run(coord.async_auto_approve_overdue()) == 0

    def test_overdue_completion_approves_itself(self):
        coord, storage, mod, kid, comp = self._pending(13)
        storage.set_setting("auto_approve_hours", 12)
        coord.hass.bus = MagicMock()
        with (
            patch("custom_components.taskmate.coord_auto_approve.dt_util.now", return_value=_now()),
            patch.object(mod.dt_util, "now", return_value=_now()),
        ):
            assert run(coord.async_auto_approve_overdue()) == 1
        stored = next(c for c in storage.get_completions() if c.id == comp.id)
        assert stored.approved and stored.auto_approved
        assert storage.get_child(kid.id).points == 2
        fired = [c.args[0] for c in coord.hass.bus.async_fire.call_args_list]
        assert "taskmate_chore_auto_approved" in fired

    def test_recent_completion_waits(self):
        coord, storage, mod, _kid, comp = self._pending(2)
        storage.set_setting("auto_approve_hours", 12)
        with patch("custom_components.taskmate.coord_auto_approve.dt_util.now", return_value=_now()):
            assert coord.overdue_completions() == []

    def test_open_ended_always_waits_for_a_parent(self):
        coord, storage, mod, _kid, comp = self._pending(48, open_ended=True)
        storage.set_setting("auto_approve_hours", 1)
        with patch("custom_components.taskmate.coord_auto_approve.dt_util.now", return_value=_now()):
            assert coord.overdue_completions() == []
