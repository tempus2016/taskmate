"""Todo platform — each child's outstanding chores as a native HA to-do list (FEAT-8).

Exposes one TodoListEntity per child, listing the chores they still need to do
today (via the shared get_due_chores_for_child). Checking an item off completes
the chore, so the native HA to-do card and voice assistants can drive TaskMate
without the custom cards.
"""

from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TaskMateCoordinator
from .entity import taskmate_device_info


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up a to-do list per child, adding new children as they appear."""
    coordinator: TaskMateCoordinator = hass.data[DOMAIN][entry.entry_id]
    tracked: set[str] = set()

    @callback
    def _add_new() -> None:
        new = []
        for child in coordinator.data.get("children", []):
            if child.id not in tracked:
                new.append(TaskMateChildTodoList(coordinator, entry, child))
                tracked.add(child.id)
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class TaskMateChildTodoList(CoordinatorEntity, TodoListEntity):
    """A child's outstanding chores as a to-do list."""

    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, coordinator, entry, child) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._child_id = child.id
        self._attr_unique_id = f"{entry.entry_id}_{child.id}_todo"
        self._attr_name = child.name

    @property
    def device_info(self) -> DeviceInfo:
        return taskmate_device_info(self._entry.entry_id)

    @property
    def todo_items(self) -> list[TodoItem]:
        if not self.coordinator.get_child(self._child_id):
            return []
        return [
            TodoItem(summary=chore.name, uid=chore.id, status=TodoItemStatus.NEEDS_ACTION)
            for chore in self.coordinator.get_due_chores_for_child(self._child_id)
        ]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Checking an item off completes the chore for this child."""
        if item.status == TodoItemStatus.COMPLETED and item.uid:
            await self.coordinator.async_complete_chore(item.uid, self._child_id)
