"""Tests for the per-child todo platform (FEAT-8)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.todo import TodoItem, TodoItemStatus

from custom_components.taskmate.models import Child, Chore
from custom_components.taskmate.todo import TaskMateChildTodoList


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _entry():
    e = MagicMock()
    e.entry_id = "e1"
    return e


def _coord(child, due=None):
    coord = MagicMock()
    coord.get_child = MagicMock(return_value=child)
    coord.get_due_chores_for_child = MagicMock(return_value=due or [])
    coord.async_complete_chore = AsyncMock()
    return coord


def test_todo_items_map_due_chores():
    child = Child(name="Malia", id="ch1")
    due = [Chore(name="Dishes", id="c1"), Chore(name="Trash", id="c2")]
    ent = TaskMateChildTodoList(_coord(child, due), _entry(), child)
    assert ent._attr_name == "Malia"
    assert ent._attr_unique_id == "e1_ch1_todo"
    items = ent.todo_items
    assert [(i.summary, i.uid, i.status) for i in items] == [
        ("Dishes", "c1", TodoItemStatus.NEEDS_ACTION),
        ("Trash", "c2", TodoItemStatus.NEEDS_ACTION),
    ]


def test_todo_items_empty_when_child_missing():
    ent = TaskMateChildTodoList(_coord(None), _entry(), Child(name="Gone", id="ch1"))
    assert ent.todo_items == []


def test_check_item_completes_chore():
    child = Child(name="Malia", id="ch1")
    coord = _coord(child)
    ent = TaskMateChildTodoList(coord, _entry(), child)
    run(ent.async_update_todo_item(TodoItem(summary="Dishes", uid="c1", status=TodoItemStatus.COMPLETED)))
    coord.async_complete_chore.assert_awaited_once_with("c1", "ch1")


def test_uncheck_item_does_nothing():
    child = Child(name="Malia", id="ch1")
    coord = _coord(child)
    ent = TaskMateChildTodoList(coord, _entry(), child)
    run(ent.async_update_todo_item(TodoItem(summary="Dishes", uid="c1", status=TodoItemStatus.NEEDS_ACTION)))
    coord.async_complete_chore.assert_not_awaited()
