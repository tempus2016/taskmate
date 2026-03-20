"""Binary sensor platform for Choremander integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChoremanderCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Choremander binary sensors."""
    coordinator: ChoremanderCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[BinarySensorEntity] = [
        HasPendingApprovalsBinarySensor(coordinator, entry),
    ]

    async_add_entities(entities)


class ChoremandorBaseBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for Choremander binary sensors."""

    def __init__(
        self,
        coordinator: ChoremandorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Choremander",
            manufacturer="Choremander",
            model="Family Chore Manager",
        )


class HasPendingApprovalsBinarySensor(ChoremandorBaseBinarySensor):
    """Binary sensor indicating if there are pending approvals."""

    def __init__(
        self,
        coordinator: ChoremandorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_has_pending_approvals"
        self._attr_name = "Has Pending Approvals"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """Return true if there are pending approvals."""
        pending_completions = self.coordinator.data.get("pending_completions", [])
        pending_rewards = self.coordinator.data.get("pending_reward_claims", [])
        return len(pending_completions) > 0 or len(pending_rewards) > 0

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

        return {
            "pending_chore_completions": len(pending_completions),
            "pending_reward_claims": len(pending_rewards),
            "total_pending": len(pending_completions) + len(pending_rewards),
        }
