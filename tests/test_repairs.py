"""Repairs: setups that can't work show up under Settings → Repairs and clear once fixed."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.taskmate import coord_repairs
from custom_components.taskmate.coord_repairs import RepairsMixin
from custom_components.taskmate.models import Child, Chore, ParentRecipient, Reward


class _Coord(RepairsMixin):
    def __init__(self, *, children=(), chores=(), rewards=(), parents=(), settings=None, services=(), entities=()):
        self.hass = MagicMock()
        self.hass.is_running = True
        self.hass.services.has_service = lambda d, s: f"{d}.{s}" in set(services)
        known = set(entities)
        self.hass.states.get = lambda e: MagicMock() if e in known else None
        settings = settings or {}
        self.storage = MagicMock()
        self.storage.get_setting = lambda k, d=None: settings.get(k, d)
        self.storage.get_children.return_value = list(children)
        self.storage.get_chores.return_value = list(chores)
        self.storage.get_rewards.return_value = list(rewards)
        self.storage.get_parent_recipients.return_value = list(parents)
        self.allowed = set()

    def is_unlock_allowed(self, entity_id):
        return entity_id in self.allowed


def _keys(coord):
    return {v["key"] for v in coord.find_repair_issues().values()}


def test_healthy_setup_has_no_issues():
    kid = Child(name="Vaiha", id="k1", notify_service="notify.mobile_app_vaiha", presence_entity="person.vaiha")
    coord = _Coord(
        children=[kid],
        chores=[Chore(name="Bins", id="c1", assigned_to=["k1"])],
        services=["notify.mobile_app_vaiha"],
        entities=["person.vaiha"],
    )
    assert coord.find_repair_issues() == {}


def test_missing_notify_services_are_reported_once_each():
    parent = ParentRecipient(name="John", notify_service="notify.mobile_app_old_phone")
    kid = Child(name="Vaiha", id="k1", notify_service="notify.mobile_app_old_phone")
    coord = _Coord(children=[kid], parents=[parent], settings={"notify_service": "notify.gone"})
    found = coord.find_repair_issues()
    services = sorted(v["placeholders"]["service"] for v in found.values())
    assert services == ["notify.gone", "notify.mobile_app_old_phone"]


def test_disabled_parent_is_not_checked():
    parent = ParentRecipient(name="John", notify_service="notify.gone", enabled=False)
    assert _keys(_Coord(parents=[parent])) == set()


def test_child_entity_missing():
    kid = Child(name="Vaiha", id="k1", availability_entity="binary_sensor.school", picture_entity="person.v")
    found = _Coord(children=[kid], entities=["person.v"]).find_repair_issues()
    assert list(found) == ["child_entity_missing_k1_availability_entity"]
    assert found["child_entity_missing_k1_availability_entity"]["placeholders"] == {
        "child": "Vaiha",
        "entity": "binary_sensor.school",
    }


def test_chore_problems():
    chores = [
        Chore(name="Ghost", id="c1", assigned_to=["gone"]),
        Chore(name="Everyone", id="c2", assigned_to=[]),
        Chore(name="Rainy", id="c3", weather_entity="weather.old"),
        Chore(name="Locked", id="c4", depends_on=["deleted"]),
        Chore(name="Off", id="c5", assigned_to=["gone"], enabled=False),
    ]
    found = _Coord(children=[Child(name="A", id="k1")], chores=chores).find_repair_issues()
    assert set(found) == {
        "chore_assigned_to_nobody_c1",
        "chore_entity_missing_c3_weather_entity",
        "chore_dependency_missing_c4",
    }
    assert found["chore_dependency_missing_c4"]["severity"] == "error"


def test_reward_problems():
    rewards = [
        Reward(name="Ghost", id="r1", assigned_to=["gone"]),
        Reward(name="TV", id="r2", unlock_entity="switch.tv"),
    ]
    coord = _Coord(children=[Child(name="A", id="k1")], rewards=rewards)
    assert _keys(coord) == {"reward_assigned_to_nobody", "reward_unlock_not_allowed"}
    coord.allowed.add("switch.tv")
    assert _keys(coord) == {"reward_assigned_to_nobody"}


def test_update_creates_then_clears(monkeypatch):
    created, deleted = [], []
    monkeypatch.setattr(coord_repairs.ir, "async_create_issue", lambda hass, dom, iid, **kw: created.append(iid))
    monkeypatch.setattr(coord_repairs.ir, "async_delete_issue", lambda hass, dom, iid: deleted.append(iid))
    monkeypatch.setattr(coord_repairs.ir, "async_get", lambda hass: MagicMock(issues={}))
    kid = Child(name="Vaiha", id="k1", presence_entity="person.gone")
    coord = _Coord(children=[kid])
    coord._repairs_loaded_at = -10_000  # grace period over
    coord.async_update_repairs()
    assert created == ["child_entity_missing_k1_presence_entity"]
    coord.async_update_repairs()  # unchanged: not re-created
    assert len(created) == 1
    kid.presence_entity = ""
    coord.async_update_repairs()
    assert deleted == ["child_entity_missing_k1_presence_entity"]


def test_no_checks_during_startup(monkeypatch):
    created = []
    monkeypatch.setattr(coord_repairs.ir, "async_create_issue", lambda *a, **kw: created.append(a))
    coord = _Coord(children=[Child(name="V", id="k1", presence_entity="person.gone")])
    coord.async_update_repairs()  # first call starts the grace clock
    coord.hass.is_running = False
    coord._repairs_loaded_at = -10_000
    coord.async_update_repairs()
    assert created == []
