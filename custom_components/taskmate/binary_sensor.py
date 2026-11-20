"""Binary sensor platform for TaskMate integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TaskMateCoordinator
from .entity import taskmate_device_info
from .entity_names import TranslatedNameMixin


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TaskMate binary sensors."""
    coordinator: TaskMateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = [
        HasPendingApprovalsBinarySensor(coordinator, entry),
    ]

    async_add_entities(entities)


class TaskMateBaseBinarySensor(TranslatedNameMixin, CoordinatorEntity, BinarySensorEntity):
    """Base class for TaskMate binary sensors."""

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return taskmate_device_info(self._entry.entry_id)


class HasPendingApprovalsBinarySensor(TaskMateBaseBinarySensor):
    """Binary sensor indicating if there are pending approvals."""

    def __init__(
        self,
        coordinator: TaskMateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_has_pending_approvals"
        self._set_translated_name("binary_sensor", "has_pending_approvals")

    @property
    def is_on(self) -> bool:
        """Return true if there are pending approvals."""
        pending_completions = self.coordinator.data.get("pending_completions", [])
        pending_rewards = self.coordinator.data.get("pending_reward_claims", [])
        return len(pending_completions) > 0 or len(pending_rewards) > 0 or self._pending_swaps() > 0

    def _pending_swaps(self) -> int:
        """Chore swap requests waiting for a parent (#1275)."""
        return sum(1 for r in self.coordinator.storage.get_swap_requests() if r.get("status") == "pending")

    @property
    def icon(self) -> str:
        """Return the icon."""
        if self.is_on:
            return "mdi:bell-alert"
        return "mdi:bell-check"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        pending_completions = self.coordinator.data.get("pending_completions", [])
        pending_rewards = self.coordinator.data.get("pending_reward_claims", [])

        pending_swaps = self._pending_swaps()
        return {
            "pending_chore_completions": len(pending_completions),
            "pending_reward_claims": len(pending_rewards),
            "pending_swap_requests": pending_swaps,
            "total_pending": len(pending_completions) + len(pending_rewards) + pending_swaps,
        }
