"""Multi-parent approval routing (#687).

Send approvals to whoever is home, or round-robin between parents, instead of
buzzing everyone every time. Every fallback errs towards over-notifying: an
unseen approval is worse than a redundant buzz.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.models import ParentRecipient


def _notifier(parents=(), settings=None, states=None):
    conf = dict(settings or {})
    hass = MagicMock()
    hass.services.async_call = AsyncMock()
    known = dict(states or {})
    hass.states.get = MagicMock(
        side_effect=lambda e: MagicMock(state=known[e]) if e in known else None)
    storage = MagicMock()
    storage.get_setting = MagicMock(side_effect=lambda k, d="": conf.get(k, d))
    storage.set_setting = MagicMock(side_effect=lambda k, v: conf.__setitem__(k, v))
    storage.get_parent_recipients = MagicMock(return_value=list(parents))
    n = NotificationCoordinator(hass, storage)
    n._conf = conf
    return n


def _cfg(*recipient_ids, enabled=True):
    cfg = MagicMock()
    cfg.master_enabled = True
    cfg.routes = {rid: MagicMock(enabled=enabled) for rid in recipient_ids}
    return cfg


DAD = ParentRecipient(name="Dad", notify_service="notify.dad", id="parent:dad",
                      presence_entity="device_tracker.dad")
MUM = ParentRecipient(name="Mum", notify_service="notify.mum", id="parent:mum",
                      presence_entity="device_tracker.mum")
NOENT = ParentRecipient(name="Gran", notify_service="notify.gran", id="parent:gran")


class TestMode:
    def test_defaults_to_all(self):
        assert _notifier().parent_routing_mode() == "all"

    def test_unknown_mode_falls_back_to_all(self):
        assert _notifier(settings={"parent_routing": "telepathy"}).parent_routing_mode() == "all"


class TestAllMode:
    def test_every_enabled_parent_is_chosen(self):
        n = _notifier([DAD, MUM])
        assert n._route_parents("t", _cfg("parent:dad", "parent:mum"), None) == {"parent:dad", "parent:mum"}

    def test_disabled_routes_are_skipped(self):
        n = _notifier([DAD, MUM])
        cfg = _cfg("parent:dad", "parent:mum")
        cfg.routes["parent:mum"].enabled = False
        assert n._route_parents("t", cfg, None) == {"parent:dad"}

    def test_children_are_not_parents(self):
        n = _notifier([DAD])
        assert n._route_parents("t", _cfg("child:a", "parent:dad"), None) == {"parent:dad"}


class TestHomeMode:
    def _n(self, states):
        return _notifier([DAD, MUM], {"parent_routing": "home"}, states)

    def test_only_the_parent_who_is_home(self):
        n = self._n({"device_tracker.dad": "home", "device_tracker.mum": "not_home"})
        assert n._route_parents("t", _cfg("parent:dad", "parent:mum"), None) == {"parent:dad"}

    def test_both_home_means_both(self):
        n = self._n({"device_tracker.dad": "home", "device_tracker.mum": "home"})
        assert n._route_parents("t", _cfg("parent:dad", "parent:mum"), None) == {"parent:dad", "parent:mum"}

    def test_nobody_home_falls_back_to_everyone(self):
        """An unseen approval is worse than a redundant buzz."""
        n = self._n({"device_tracker.dad": "not_home", "device_tracker.mum": "not_home"})
        assert n._route_parents("t", _cfg("parent:dad", "parent:mum"), None) == {"parent:dad", "parent:mum"}

    def test_missing_presence_entity_counts_as_available(self):
        """A parent who never configured presence must not be silently cut out."""
        n = _notifier([NOENT], {"parent_routing": "home"}, {})
        assert n._route_parents("t", _cfg("parent:gran"), None) == {"parent:gran"}

    def test_broken_presence_sensor_fails_open(self):
        n = self._n({"device_tracker.dad": "unavailable", "device_tracker.mum": "not_home"})
        assert "parent:dad" in n._route_parents("t", _cfg("parent:dad", "parent:mum"), None)

    @pytest.mark.parametrize("value", ["home", "on", "true", "present", "HOME"])
    def test_states_that_count_as_home(self, value):
        n = self._n({"device_tracker.dad": value, "device_tracker.mum": "not_home"})
        assert n._route_parents("t", _cfg("parent:dad", "parent:mum"), None) == {"parent:dad"}


class TestRoundRobin:
    def _n(self):
        return _notifier([DAD, MUM], {"parent_routing": "round_robin"})

    def test_one_parent_at_a_time(self):
        n = self._n()
        chosen = n._route_parents("t", _cfg("parent:dad", "parent:mum"), None)
        assert len(chosen) == 1

    def test_it_actually_rotates(self):
        n = self._n()
        cfg = _cfg("parent:dad", "parent:mum")
        first = n._route_parents("t", cfg, None)
        second = n._route_parents("t", cfg, None)
        third = n._route_parents("t", cfg, None)
        assert first != second
        assert third == first  # wraps

    def test_rotation_is_per_notification_type(self):
        """A reward claim shouldn't advance the chore-approval rotation."""
        n = self._n()
        cfg = _cfg("parent:dad", "parent:mum")
        n._route_parents("chore", cfg, None)
        assert n._conf["parent_routing_state"].keys() == {"chore"}
        n._route_parents("reward", cfg, None)
        assert n._conf["parent_routing_state"].keys() == {"chore", "reward"}

    def test_a_removed_parent_does_not_wedge_the_rotation(self):
        n = self._n()
        n._conf["parent_routing_state"] = {"t": "parent:gone"}
        chosen = n._route_parents("t", _cfg("parent:dad", "parent:mum"), None)
        assert chosen and chosen.issubset({"parent:dad", "parent:mum"})

    def test_single_parent_always_gets_it(self):
        n = _notifier([DAD], {"parent_routing": "round_robin"})
        cfg = _cfg("parent:dad")
        assert n._route_parents("t", cfg, None) == {"parent:dad"}
        assert n._route_parents("t", cfg, None) == {"parent:dad"}


class TestModel:
    def test_presence_entity_round_trips(self):
        restored = ParentRecipient.from_dict(DAD.to_dict())
        assert restored.presence_entity == "device_tracker.dad"

    def test_legacy_parent_without_presence(self):
        restored = ParentRecipient.from_dict({"name": "Old", "notify_service": "notify.x"})
        assert restored.presence_entity == ""
