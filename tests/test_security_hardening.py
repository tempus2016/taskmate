"""Regression tests for the authorization / input-hardening pass.

These lock in that the "second doors" into privileged operations — the entity
platforms, the mobile-action event bus, and backup import — enforce the same
checks as the WebSocket/service layer, and that a few input-validation gaps
stay closed.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import Unauthorized

from custom_components.taskmate import authz
from custom_components.taskmate.button import ClaimRewardButton, CompleteChoreButton
from custom_components.taskmate.coord_notifications import NotificationCoordinator
from custom_components.taskmate.models import Child, Chore, Reward
from custom_components.taskmate.number import TaskMateSettingNumber
from custom_components.taskmate.select import TaskMateSettingSelect
from custom_components.taskmate.storage import TaskMateStorage
from custom_components.taskmate.todo import TaskMateChildTodoList


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _ctx(user_id):
    c = MagicMock()
    c.user_id = user_id
    return c


def _hass(user):
    hass = MagicMock()
    hass.auth.async_get_user = AsyncMock(return_value=user)
    return hass


def _entry():
    e = MagicMock()
    e.entry_id = "e1"
    return e


# ── authz helpers (parity with the service-layer gate) ──────────────────────


def test_context_is_admin_trusts_contextless():
    assert run(authz.async_context_is_admin(_hass(None), None)) is True
    assert run(authz.async_context_is_admin(_hass(None), _ctx(""))) is True


def test_context_is_admin_rejects_non_admin():
    hass = _hass(MagicMock(is_admin=False))
    assert run(authz.async_context_is_admin(hass, _ctx("u1"))) is False


def test_context_is_parent_accepts_configured_parent():
    coord = MagicMock()
    coord.storage.get_parent_user_ids.return_value = ["parent-1"]
    hass = _hass(MagicMock(is_admin=False))
    assert run(authz.async_context_is_parent(hass, coord, _ctx("parent-1"))) is True
    assert run(authz.async_context_is_parent(hass, coord, _ctx("stranger"))) is False


def test_allows_child_blocks_cross_child():
    coord = MagicMock()
    coord.get_child.return_value = MagicMock(linked_user_id="uid-malia")
    coord.storage.get_children.return_value = []
    hass = _hass(MagicMock(is_admin=False))
    # Ella's HA user acting as Malia (who is linked to someone else) → denied.
    assert run(authz.async_context_allows_child(hass, coord, _ctx("uid-ella"), "malia")) is False
    # Malia's own linked user → allowed.
    assert run(authz.async_context_allows_child(hass, coord, _ctx("uid-malia"), "malia")) is True


# ── entity platforms enforce the gate ───────────────────────────────────────


def test_number_rejects_non_admin():
    coord = MagicMock()
    store = {}
    coord.storage.set_setting = MagicMock(side_effect=store.__setitem__)
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    num = TaskMateSettingNumber(
        coord, _entry(), "weekend_multiplier", "weekend_multiplier", 1.0, 5.0, 0.5, 1.0, "mdi:x"
    )
    num.hass = _hass(MagicMock(is_admin=False))
    num._context = _ctx("child-user")
    with pytest.raises(Unauthorized):
        run(num.async_set_native_value(5.0))
    assert store == {}  # nothing persisted


def test_select_rejects_non_admin():
    coord = MagicMock()
    store = {}
    coord.storage.set_setting = MagicMock(side_effect=store.__setitem__)
    coord.storage.async_save = AsyncMock()
    coord.async_refresh = AsyncMock()
    sel = TaskMateSettingSelect(
        coord, _entry(), "streak_reset_mode", "streak_reset_mode", ["reset", "pause"], "reset", "mdi:x"
    )
    sel.hass = _hass(MagicMock(is_admin=False))
    sel._context = _ctx("child-user")
    with pytest.raises(Unauthorized):
        run(sel.async_select_option("pause"))
    assert store == {}


def test_claim_reward_button_rejects_cross_child():
    child = Child(name="Malia", id="malia", linked_user_id="uid-malia")
    reward = Reward(name="Cinema", cost=100, id="rw1")
    coord = MagicMock()
    coord.get_child.return_value = child
    coord.get_reward.return_value = reward
    coord.storage.get_children.return_value = [child]
    coord.async_claim_reward = AsyncMock()
    btn = ClaimRewardButton(coord, _entry(), child, reward)
    btn.hass = _hass(MagicMock(is_admin=False))
    btn._context = _ctx("uid-ella")  # a different child's HA user
    with pytest.raises(Unauthorized):
        run(btn.async_press())
    coord.async_claim_reward.assert_not_called()


def test_complete_chore_button_rejects_cross_child():
    child = Child(name="Malia", id="malia", linked_user_id="uid-malia")
    chore = Chore(name="Dishes", id="cho1")
    coord = MagicMock()
    coord.get_child.return_value = child
    coord.get_chore.return_value = chore
    coord.storage.get_children.return_value = [child]
    coord.async_complete_chore = AsyncMock()
    btn = CompleteChoreButton(coord, _entry(), child, chore)
    btn.hass = _hass(MagicMock(is_admin=False))
    btn._context = _ctx("uid-ella")
    with pytest.raises(Unauthorized):
        run(btn.async_press())
    coord.async_complete_chore.assert_not_called()


def test_todo_rejects_cross_child():
    child = Child(name="Malia", id="malia", linked_user_id="uid-malia")
    coord = MagicMock()
    coord.get_child.return_value = child
    coord.storage.get_children.return_value = [child]
    coord.async_complete_chore = AsyncMock()
    lst = TaskMateChildTodoList(coord, _entry(), child)
    lst.hass = _hass(MagicMock(is_admin=False))
    lst._context = _ctx("uid-ella")
    item = MagicMock()
    item.status = "completed"
    item.uid = "cho1"
    with pytest.raises(Unauthorized):
        run(lst.async_update_todo_item(item))
    coord.async_complete_chore.assert_not_called()


# ── mobile-action event handler is parent-gated ─────────────────────────────


def _notif_with_coordinator(parent_ids, user):
    nc = NotificationCoordinator(_hass(user), MagicMock())
    nc.coordinator = MagicMock()
    # authz reads coordinator.storage.get_parent_user_ids(), so wire it there.
    nc.coordinator.storage.get_parent_user_ids.return_value = parent_ids
    nc.coordinator.async_approve_chore = AsyncMock()
    nc.coordinator.async_approve_reward = AsyncMock()
    return nc


def _event(action, user_id):
    ev = MagicMock()
    ev.data = {"action": action}
    ev.context.user_id = user_id
    return ev


def test_mobile_action_ignored_from_non_parent():
    nc = _notif_with_coordinator(parent_ids=["parent-1"], user=MagicMock(is_admin=False))
    run(nc.handle_mobile_action(_event("TASKMATE_APPROVE_abc", "child-user")))
    nc.coordinator.async_approve_chore.assert_not_called()
    nc.coordinator.async_approve_reward.assert_not_called()


def test_mobile_action_allowed_from_parent():
    nc = _notif_with_coordinator(parent_ids=["parent-1"], user=MagicMock(is_admin=False))
    run(nc.handle_mobile_action(_event("TASKMATE_APPROVE_abc", "parent-1")))
    nc.coordinator.async_approve_chore.assert_called_once_with("abc")


# ── backup import re-validates untrusted records ────────────────────────────


def _storage():
    return TaskMateStorage.__new__(TaskMateStorage)


def test_import_normalises_crafted_enum_and_urls():
    st = _storage()
    st.import_data(
        {
            "chores": [
                {
                    "id": "c1",
                    "name": "Tidy",
                    "assignment_mode": 'a"><img src=x onerror=alert(1)>',
                    "schedule_mode": "bogus",
                    "image_url": "https://evil.example/track.png",
                }
            ],
            "task_groups": [{"id": "g1", "policy": '"><script>'}],
            "badges": [{"id": "b1", "tier": '"><script>'}],
            "settings": {
                "history_days": '1" onfocus=alert(1) autofocus x="',
                "streak_reset_mode": '"><img>',
            },
        }
    )
    chore = st._data["chores"][0]
    assert chore["assignment_mode"] == "everyone"
    assert chore["schedule_mode"] == "specific_days"
    assert chore["image_url"] == ""
    assert st._data["task_groups"][0]["policy"] == "sticky"
    assert st._data["badges"][0]["tier"] == "bronze"
    # A non-numeric numeric-setting is dropped (default applies), never rendered raw.
    assert "history_days" not in st._data["settings"]
    assert "streak_reset_mode" not in st._data["settings"]


def test_import_coerces_numeric_string():
    st = _storage()
    st.import_data({"settings": {"weekend_multiplier": "2.5"}})
    assert st._data["settings"]["weekend_multiplier"] == 2.5


# ── smaller input-hardening gaps ────────────────────────────────────────────


def test_ics_escape_neutralises_carriage_return():
    from custom_components.taskmate.ics import _escape

    assert _escape("a\rb") == "a\\nb"
    assert _escape("a\r\nb") == "a\\nb"
    assert _escape("a\nb") == "a\\nb"


def test_timed_start_eligibility():
    from custom_components.taskmate.coordinator import TaskMateCoordinator

    coord = object.__new__(TaskMateCoordinator)
    everyone = Chore(name="Piano", task_type="timed", id="t1")
    assert coord._timed_start_allowed(everyone, "malia") is True

    disabled = Chore(name="Piano", task_type="timed", id="t2", enabled=False)
    assert coord._timed_start_allowed(disabled, "malia") is False

    assigned_other = Chore(name="Piano", task_type="timed", id="t3", assigned_to=["ella"])
    assert coord._timed_start_allowed(assigned_other, "malia") is False
    assert coord._timed_start_allowed(assigned_other, "ella") is True
