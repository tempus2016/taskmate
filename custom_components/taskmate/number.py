"""Number platform — expose key numeric TaskMate settings as entities (FEAT-9).

Lets the points-bearing knobs be read and changed from automations/scripts and
the HA UI without a service call. Values are persisted through the same
settings store the panel uses, so panel and entity stay in sync.
"""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import authz
from .const import DOMAIN
from .coordinator import TaskMateCoordinator
from .entity import taskmate_device_info

# (setting_key, translation_key, min, max, step, default, icon)
_NUMBERS = [
    ("weekend_multiplier", "weekend_multiplier", 1.0, 5.0, 0.5, 2.0, "mdi:calendar-weekend"),
    ("perfect_week_bonus", "perfect_week_bonus", 0, 1000, 1, 50, "mdi:trophy-award"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up the TaskMate setting-number entities."""
    coordinator: TaskMateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(TaskMateSettingNumber(coordinator, entry, *cfg) for cfg in _NUMBERS)


class TaskMateSettingNumber(CoordinatorEntity, NumberEntity):
    """A single numeric TaskMate setting surfaced as a number entity."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry, key, tkey, mn, mx, step, default, icon) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._default = default
        self._attr_translation_key = tkey
        self._attr_unique_id = f"{entry.entry_id}_setting_{key}"
        self._attr_native_min_value = mn
        self._attr_native_max_value = mx
        self._attr_native_step = step
        self._attr_icon = icon

    @property
    def device_info(self) -> DeviceInfo:
        return taskmate_device_info(self._entry.entry_id)

    @property
    def native_value(self) -> float:
        raw = self.coordinator.storage.get_setting(self._key, self._default)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return float(self._default)

    async def async_set_native_value(self, value: float) -> None:
        # These entities write panel settings that are admin-only over the
        # WebSocket; enforce the same gate here so a non-admin call_service
        # can't retune the point economy.
        ctx = getattr(self, "_context", None)
        if not await authz.async_context_is_admin(getattr(self, "hass", None), ctx):
            raise Unauthorized(context=ctx)
        stored = int(value) if float(value).is_integer() else value
        self.coordinator.storage.set_setting(self._key, stored)
        await self.coordinator.storage.async_save()
        await self.coordinator.async_refresh()
