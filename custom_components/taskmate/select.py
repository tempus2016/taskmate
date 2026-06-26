"""Select platform — expose key choice TaskMate settings as entities (FEAT-9)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TaskMateCoordinator

# (setting_key, translation_key, options, default, icon)
_SELECTS = [
    ("streak_reset_mode", "streak_reset_mode", ["reset", "pause"], "reset", "mdi:restart"),
    ("card_design", "card_design", ["classic", "playroom", "console", "cleanpro"], "classic", "mdi:palette"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the TaskMate setting-select entities."""
    coordinator: TaskMateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(TaskMateSettingSelect(coordinator, entry, *cfg) for cfg in _SELECTS)


class TaskMateSettingSelect(CoordinatorEntity, SelectEntity):
    """A single choice TaskMate setting surfaced as a select entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, tkey, options, default, icon) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._key = key
        self._default = default
        self._attr_translation_key = tkey
        self._attr_unique_id = f"{entry.entry_id}_setting_{key}"
        self._attr_options = options
        self._attr_icon = icon

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="TaskMate",
            manufacturer="TaskMate",
            model="Family Chore Manager",
        )

    @property
    def current_option(self) -> str:
        val = str(self.coordinator.storage.get_setting(self._key, self._default))
        return val if val in self._attr_options else self._default

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            return
        self.coordinator.storage.set_setting(self._key, option)
        await self.coordinator.storage.async_save()
        await self.coordinator.async_refresh()
