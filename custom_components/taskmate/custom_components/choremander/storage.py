"""Storage management for Choremander integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .models import Child, Chore, ChoreCompletion, Reward, RewardClaim

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.storage"


class ChoremanderStorage:
    """Manage Choremander data storage."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize storage."""
        self.hass = hass
        self.entry_id = entry_id
        self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry_id}")
        self._data: dict[str, Any] = {}

    async def async_load(self) -> dict[str, Any]:
        """Load data from storage."""
        data = await self._store.async_load()
        if data is None:
            data = {
                "children": [],
                "chores": [],
                "rewards": [],
                "completions": [],
                "reward_claims": [],
                "points_name": "Stars",
                "points_icon": "mdi:star",
            }
        self._data = data

        # Run data migrations
        await self._migrate_assigned_to_child_ids()

        return data

    async def _migrate_assigned_to_child_ids(self) -> None:
        """Migrate chore assigned_to from child names to child IDs if needed.

        This handles legacy data where assigned_to might contain child names
        instead of child IDs.
        """
        children = self._data.get("children", [])
        chores = self._data.get("chores", [])

        if not children or not chores:
            return

        # Build a map of child name -> child ID for migration
        name_to_id = {}
        valid_ids = set()
        for child in children:
            child_id = child.get("id", "")
            child_name = child.get("name", "")
            if child_id:
                valid_ids.add(child_id)
            if child_name and child_id:
                name_to_id[child_name] = child_id

        # Check and migrate each chore's assigned_to
        data_modified = False
        for chore in chores:
            assigned_to = chore.get("assigned_to", [])
            if not assigned_to:
                continue

            new_assigned_to = []
            chore_modified = False

            for assignment in assigned_to:
                if assignment in valid_ids:
                    # Already a valid child ID
                    new_assigned_to.append(assignment)
                elif assignment in name_to_id:
                    # This is a child name, convert to ID
                    new_assigned_to.append(name_to_id[assignment])
                    chore_modified = True
                    _LOGGER.warning(
                        "Migrating chore '%s' assigned_to: '%s' -> '%s' (name to ID)",
                        chore.get("name", "unknown"),
                        assignment,
                        name_to_id[assignment]
                    )
                else:
                    # Unknown value, keep it but log a warning
                    new_assigned_to.append(assignment)
                    _LOGGER.warning(
                        "Chore '%s' has unknown assigned_to value: '%s'",
                        chore.get("name", "unknown"),
                        assignment
                    )

            if chore_modified:
                chore["assigned_to"] = new_assigned_to
                data_modified = True

        if data_modified:
            _LOGGER.info("Data migration completed: converted child names to IDs in assigned_to")
            await self.async_save()

    async def async_save(self) -> None:
        """Save data to storage."""
        await self._store.async_save(self._data)

    @property
    def data(self) -> dict[str, Any]:
        """Return current data."""
        return self._data

    # Children management
    def get_children(self) -> list[Child]:
        """Get all children."""
        return [Child.from_dict(c) for c in self._data.get("children", [])]

    def get_child(self, child_id: str) -> Child | None:
        """Get a child by ID."""
        for child_data in self._data.get("children", []):
            if child_data.get("id") == child_id:
                return Child.from_dict(child_data)
        return None

    def add_child(self, child: Child) -> None:
        """Add a child."""
        if "children" not in self._data:
            self._data["children"] = []
        self._data["children"].append(child.to_dict())

    def update_child(self, child: Child) -> None:
        """Update a child."""
        children = self._data.get("children", [])
        for i, c in enumerate(children):
            if c.get("id") == child.id:
                children[i] = child.to_dict()
                return
        # If not found, add it
        self.add_child(child)

    def remove_child(self, child_id: str) -> None:
        """Remove a child."""
        self._data["children"] = [
            c for c in self._data.get("children", []) if c.get("id") != child_id
        ]

    # Chores management
    def get_chores(self) -> list[Chore]:
        """Get all chores."""
        return [Chore.from_dict(c) for c in self._data.get("chores", [])]

    def get_chore(self, chore_id: str) -> Chore | None:
        """Get a chore by ID."""
        for chore_data in self._data.get("chores", []):
            if chore_data.get("id") == chore_id:
                return Chore.from_dict(chore_data)
        return None

    def add_chore(self, chore: Chore) -> None:
        """Add a chore."""
        if "chores" not in self._data:
            self._data["chores"] = []
        self._data["chores"].append(chore.to_dict())

    def update_chore(self, chore: Chore) -> None:
        """Update a chore."""
        chores = self._data.get("chores", [])
        for i, c in enumerate(chores):
            if c.get("id") == chore.id:
                chores[i] = chore.to_dict()
                return
        self.add_chore(chore)

    def remove_chore(self, chore_id: str) -> None:
        """Remove a chore."""
        self._data["chores"] = [
            c for c in self._data.get("chores", []) if c.get("id") != chore_id
        ]

    # Rewards management
    def get_rewards(self) -> list[Reward]:
        """Get all rewards."""
        return [Reward.from_dict(r) for r in self._data.get("rewards", [])]

    def get_reward(self, reward_id: str) -> Reward | None:
        """Get a reward by ID."""
        for reward_data in self._data.get("rewards", []):
            if reward_data.get("id") == reward_id:
                return Reward.from_dict(reward_data)
        return None

    def add_reward(self, reward: Reward) -> None:
        """Add a reward."""
        if "rewards" not in self._data:
            self._data["rewards"] = []
        self._data["rewards"].append(reward.to_dict())

    def update_reward(self, reward: Reward) -> None:
        """Update a reward."""
        rewards = self._data.get("rewards", [])
        for i, r in enumerate(rewards):
            if r.get("id") == reward.id:
                rewards[i] = reward.to_dict()
                return
        self.add_reward(reward)

    def remove_reward(self, reward_id: str) -> None:
        """Remove a reward."""
        self._data["rewards"] = [
            r for r in self._data.get("rewards", []) if r.get("id") != reward_id
        ]

    # Completions management
    def get_completions(self) -> list[ChoreCompletion]:
        """Get all chore completions."""
        return [ChoreCompletion.from_dict(c) for c in self._data.get("completions", [])]

    def get_pending_completions(self) -> list[ChoreCompletion]:
        """Get pending (unapproved) completions."""
        return [c for c in self.get_completions() if not c.approved]

    def add_completion(self, completion: ChoreCompletion) -> None:
        """Add a completion record."""
        if "completions" not in self._data:
            self._data["completions"] = []
        self._data["completions"].append(completion.to_dict())

    def update_completion(self, completion: ChoreCompletion) -> None:
        """Update a completion record."""
        completions = self._data.get("completions", [])
        for i, c in enumerate(completions):
            if c.get("id") == completion.id:
                completions[i] = completion.to_dict()
                return

    def remove_completion(self, completion_id: str) -> None:
        """Remove a completion record."""
        self._data["completions"] = [
            c for c in self._data.get("completions", []) if c.get("id") != completion_id
        ]

    # Reward claims management
    def get_reward_claims(self) -> list[RewardClaim]:
        """Get all reward claims."""
        return [RewardClaim.from_dict(r) for r in self._data.get("reward_claims", [])]

    def get_pending_reward_claims(self) -> list[RewardClaim]:
        """Get pending (unapproved) reward claims."""
        return [c for c in self.get_reward_claims() if not c.approved]

    def add_reward_claim(self, claim: RewardClaim) -> None:
        """Add a reward claim."""
        if "reward_claims" not in self._data:
            self._data["reward_claims"] = []
        self._data["reward_claims"].append(claim.to_dict())

    def update_reward_claim(self, claim: RewardClaim) -> None:
        """Update a reward claim."""
        claims = self._data.get("reward_claims", [])
        for i, c in enumerate(claims):
            if c.get("id") == claim.id:
                claims[i] = claim.to_dict()
                return

    # Settings
    def get_points_name(self) -> str:
        """Get the points currency name."""
        return self._data.get("points_name", "Stars")

    def set_points_name(self, name: str) -> None:
        """Set the points currency name."""
        self._data["points_name"] = name

    def get_points_icon(self) -> str:
        """Get the points icon."""
        return self._data.get("points_icon", "mdi:star")

    def set_points_icon(self, icon: str) -> None:
        """Set the points icon."""
        self._data["points_icon"] = icon
