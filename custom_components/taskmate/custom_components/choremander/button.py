"""Button platform for Choremander integration."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChoremanderCoordinator
from .models import Child, Chore, Reward

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Choremander buttons."""
    coordinator: ChoremanderCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[ButtonEntity] = []

    # Add complete chore buttons for each child/chore combination
    children = coordinator.data.get("children", [])
    chores = coordinator.data.get("chores", [])
    rewards = coordinator.data.get("rewards", [])

    for child in children:
        # Chore completion buttons
        for chore in chores:
            # Only create button if chore is assigned to this child or all children
            if not chore.assigned_to or child.id in chore.assigned_to:
                entities.append(
                    CompleteChoreButton(coordinator, entry, child, chore)
                )

        # Reward claim buttons
        for reward in rewards:
            entities.append(
                ClaimRewardButton(coordinator, entry, child, reward)
            )

    async_add_entities(entities)

    # Set up listener for updates
    @callback
    def async_update_entities() -> None:
        """Update entities when data changes."""
        # This is called when coordinator updates
        pass

    coordinator.async_add_listener(async_update_entities)


class ChoremandorBaseButton(CoordinatorEntity, ButtonEntity):
    """Base class for Choremander buttons."""

    def __init__(
        self,
        coordinator: ChoremandorCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the button."""
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


class CompleteChoreButton(ChoremandorBaseButton):
    """Button to mark a chore as completed."""

    def __init__(
        self,
        coordinator: ChoremandorCoordinator,
        entry: ConfigEntry,
        child: Child,
        chore: Chore,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)
        self.child_id = child.id
        self.chore_id = chore.id
        self._attr_unique_id = f"{entry.entry_id}_{child.id}_{chore.id}_complete"
        self._attr_name = f"{child.name}: Complete {chore.name}"

    @property
    def icon(self) -> str:
        """Return the icon."""
        chore = self.coordinator.get_chore(self.chore_id)
        return getattr(chore, 'icon', "mdi:check-circle") if chore else "mdi:check-circle"

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        child = self.coordinator.get_child(self.child_id)
        chore = self.coordinator.get_chore(self.chore_id)

        if not child or not chore:
            return {}

        return {
            "child_id": child.id,
            "child_name": child.name,
            "chore_id": chore.id,
            "chore_name": chore.name,
            "points": chore.points,
            "requires_approval": chore.requires_approval,
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.async_complete_chore(self.chore_id, self.child_id)
        except ValueError as err:
            _LOGGER.error("Failed to complete chore: %s", err)


class ClaimRewardButton(ChoremandorBaseButton):
    """Button to claim a reward."""

    def __init__(
        self,
        coordinator: ChoremandorCoordinator,
        entry: ConfigEntry,
        child: Child,
        reward: Reward,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)
        self.child_id = child.id
        self.reward_id = reward.id
        self._attr_unique_id = f"{entry.entry_id}_{child.id}_{reward.id}_claim"
        self._attr_name = f"{child.name}: Claim {reward.name}"

    @property
    def icon(self) -> str:
        """Return the icon."""
        reward = self.coordinator.get_reward(self.reward_id)
        return reward.icon if reward else "mdi:gift"

    def _get_effective_cost(self, reward: Reward) -> int:
        """Get the effective cost for this child (dynamic or override)."""
        costs = self.coordinator.calculate_dynamic_reward_costs(reward)
        return costs.get(self.child_id, reward.cost)

    @property
    def available(self) -> bool:
        """Return if button is available."""
        child = self.coordinator.get_child(self.child_id)
        reward = self.coordinator.get_reward(self.reward_id)

        if not child or not reward:
            return False

        effective_cost = self._get_effective_cost(reward)
        return child.points >= effective_cost

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional attributes."""
        child = self.coordinator.get_child(self.child_id)
        reward = self.coordinator.get_reward(self.reward_id)

        if not child or not reward:
            return {}

        effective_cost = self._get_effective_cost(reward)
        can_afford = child.points >= effective_cost

        return {
            "child_id": child.id,
            "child_name": child.name,
            "reward_id": reward.id,
            "reward_name": reward.name,
            "cost": effective_cost,
            "override_cost": reward.cost,
            "is_dynamic": not getattr(reward, 'override_point_value', False),
            "child_points": child.points,
            "can_afford": can_afford,
            "points_needed": max(0, effective_cost - child.points),
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.coordinator.async_claim_reward(self.reward_id, self.child_id)
        except ValueError as err:
            _LOGGER.error("Failed to claim reward: %s", err)


class ApproveChoreButton(ChoremandorBaseButton):
    """Button to approve a chore completion."""

    def __init__(
        self,
        coordinator: ChoremandorCoordinator,
        entry: ConfigEntry,
        completion_id: str,
        child_name: str,
        chore_name: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)
        self.completion_id = completion_id
        self._attr_unique_id = f"{entry.entry_id}_{completion_id}_approve"
        self._attr_name = f"Approve: {child_name} - {chore_name}"
        self._attr_icon = "mdi:check-circle"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_approve_chore(self.completion_id)


class RejectChoreButton(ChoremandorBaseButton):
    """Button to reject a chore completion."""

    def __init__(
        self,
        coordinator: ChoremandorCoordinator,
        entry: ConfigEntry,
        completion_id: str,
        child_name: str,
        chore_name: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entry)
        self.completion_id = completion_id
        self._attr_unique_id = f"{entry.entry_id}_{completion_id}_reject"
        self._attr_name = f"Reject: {child_name} - {chore_name}"
        self._attr_icon = "mdi:close-circle"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_reject_chore(self.completion_id)
