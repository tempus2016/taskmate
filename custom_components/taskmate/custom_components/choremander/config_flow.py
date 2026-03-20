"""Config flow for Choremander integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    AVATAR_OPTIONS,
    COMPLETION_SOUND_OPTIONS,
    DAYS_OF_WEEK,
    DEFAULT_COMPLETION_SOUND,
    DEFAULT_POINTS_ICON,
    DEFAULT_POINTS_NAME,
    DOMAIN,
    REWARD_ICON_OPTIONS,
    TIME_CATEGORIES,
    TIME_CATEGORY_ICONS,
)

_LOGGER = logging.getLogger(__name__)


class ChoremanderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Choremander."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if already configured
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title="Choremander",
                data={
                    "points_name": user_input.get("points_name", DEFAULT_POINTS_NAME),
                    "points_icon": user_input.get("points_icon", DEFAULT_POINTS_ICON),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("points_name", default=DEFAULT_POINTS_NAME): str,
                    vol.Optional("points_icon", default=DEFAULT_POINTS_ICON): selector.IconSelector(),
                }
            ),
            errors=errors,
            description_placeholders={
                "title": "Welcome to Choremander!",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ChoremanderOptionsFlow:
        """Create the options flow."""
        return ChoremanderOptionsFlow(config_entry)


class ChoremanderOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Choremander."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._selected_child_id: str | None = None
        self._selected_chore_id: str | None = None
        self._selected_reward_id: str | None = None

    @property
    def coordinator(self):
        """Get the coordinator."""
        return self.hass.data[DOMAIN][self.config_entry.entry_id]

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options - main menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "manage_children": "Manage Children",
                "manage_chores": "Manage Chores",
                "manage_rewards": "Manage Rewards",
                "settings": "Settings",
            },
        )

    # ==================== CHILDREN MANAGEMENT ====================

    async def async_step_manage_children(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage children menu."""
        children = self.coordinator.storage.get_children()
        menu_options = {"add_child": "Add New Child"}

        for child in children:
            menu_options[f"edit_child_{child.id}"] = f"Edit: {child.name}"

        menu_options["init"] = "Back to Main Menu"

        return self.async_show_menu(
            step_id="manage_children",
            menu_options=menu_options,
        )

    async def async_step_add_child(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new child."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get("name", "").strip()
            if not name:
                errors["name"] = "name_required"
            else:
                await self.coordinator.async_add_child(
                    name=name,
                    avatar=user_input.get("avatar", "mdi:account-circle"),
                )
                return await self.async_step_manage_children()

        return self.async_show_form(
            step_id="add_child",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Optional("avatar", default="mdi:account-circle"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=icon, label=icon.replace("mdi:", "").replace("-", " ").title())
                                for icon in AVATAR_OPTIONS
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_edit_child(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit a child."""
        child = self.coordinator.get_child(self._selected_child_id)
        if not child:
            return await self.async_step_manage_children()

        errors: dict[str, str] = {}

        if user_input is not None:
            action = user_input.get("action")
            if action == "delete":
                await self.coordinator.async_remove_child(child.id)
                return await self.async_step_manage_children()
            elif action == "save":
                child.name = user_input.get("name", child.name)
                child.avatar = user_input.get("avatar", child.avatar)
                await self.coordinator.async_update_child(child)
                return await self.async_step_manage_children()

        return self.async_show_form(
            step_id="edit_child",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default=child.name): str,
                    vol.Optional("avatar", default=child.avatar): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=icon, label=icon.replace("mdi:", "").replace("-", " ").title())
                                for icon in AVATAR_OPTIONS
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required("action", default="save"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="save", label="Save Changes"),
                                selector.SelectOptionDict(value="delete", label="Delete Child"),
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={"child_name": child.name},
        )

    # ==================== CHORES MANAGEMENT ====================

    async def async_step_manage_chores(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage chores menu."""
        chores = self.coordinator.storage.get_chores()
        menu_options = {
            "add_chore": "Add Single Chore",
            "add_chores_bulk": "Add Multiple Chores",
        }

        for chore in chores:
            time_label = f" [{chore.time_category}]" if chore.time_category != "anytime" else ""
            menu_options[f"edit_chore_{chore.id}"] = f"Edit: {chore.name} ({chore.points} pts){time_label}"

        menu_options["init"] = "Back to Main Menu"

        return self.async_show_menu(
            step_id="manage_chores",
            menu_options=menu_options,
        )

    async def async_step_add_chore(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new chore."""
        errors: dict[str, str] = {}
        children = self.coordinator.storage.get_children()

        if user_input is not None:
            name = user_input.get("name", "").strip()
            if not name:
                errors["name"] = "name_required"
            else:
                await self.coordinator.async_add_chore(
                    name=name,
                    points=int(user_input.get("points", 10)),
                    description=user_input.get("description", ""),
                    due_days=user_input.get("due_days", []),
                    assigned_to=user_input.get("assigned_to", []),
                    requires_approval=user_input.get("requires_approval", True),
                    time_category=user_input.get("time_category", "anytime"),
                    daily_limit=int(user_input.get("daily_limit", 1)),
                    completion_percentage_per_month=int(user_input.get("completion_percentage_per_month", 100)),
                    completion_sound=user_input.get("completion_sound", DEFAULT_COMPLETION_SOUND),
                )
                return await self.async_step_manage_chores()

        child_options = [
            selector.SelectOptionDict(value=c.id, label=c.name)
            for c in children
        ]

        day_options = [
            selector.SelectOptionDict(value=day, label=day.title())
            for day in DAYS_OF_WEEK
        ]

        time_options = [
            selector.SelectOptionDict(value=tc, label=tc.title())
            for tc in TIME_CATEGORIES
        ]

        schema_dict = {
            vol.Required("name"): str,
            vol.Optional("description", default=""): str,
            vol.Required("points", default=10): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=1000, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("time_category", default="anytime"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=time_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("due_days", default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=day_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            ),
            vol.Required("requires_approval", default=True): bool,
            vol.Required("daily_limit", default=1): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("completion_percentage_per_month", default=100): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional("completion_sound", default=DEFAULT_COMPLETION_SOUND): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=sound, label=sound.title() if sound != "none" else "No Sound")
                        for sound in COMPLETION_SOUND_OPTIONS
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }

        if child_options:
            schema_dict[vol.Optional("assigned_to", default=[])] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=child_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            )

        return self.async_show_form(
            step_id="add_chore",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_add_chores_bulk(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add multiple chores at once."""
        errors: dict[str, str] = {}
        children = self.coordinator.storage.get_children()

        if user_input is not None:
            chore_names_raw = user_input.get("chore_names", "").strip()
            if not chore_names_raw:
                errors["chore_names"] = "name_required"
            else:
                # Split by newlines or commas
                chore_names = []
                for line in chore_names_raw.replace(",", "\n").split("\n"):
                    name = line.strip()
                    if name:
                        chore_names.append(name)

                if not chore_names:
                    errors["chore_names"] = "name_required"
                else:
                    chores = await self.coordinator.async_add_chores_bulk(
                        chore_names=chore_names,
                        points=int(user_input.get("points", 10)),
                        due_days=user_input.get("due_days", []),
                        assigned_to=user_input.get("assigned_to", []),
                        requires_approval=user_input.get("requires_approval", True),
                        time_category=user_input.get("time_category", "anytime"),
                        daily_limit=int(user_input.get("daily_limit", 1)),
                        completion_percentage_per_month=int(user_input.get("completion_percentage_per_month", 100)),
                        completion_sound=user_input.get("completion_sound", DEFAULT_COMPLETION_SOUND),
                    )
                    return await self.async_step_manage_chores()

        child_options = [
            selector.SelectOptionDict(value=c.id, label=c.name)
            for c in children
        ]

        day_options = [
            selector.SelectOptionDict(value=day, label=day.title())
            for day in DAYS_OF_WEEK
        ]

        time_options = [
            selector.SelectOptionDict(value=tc, label=tc.title())
            for tc in TIME_CATEGORIES
        ]

        schema_dict = {
            vol.Required("chore_names"): selector.TextSelector(
                selector.TextSelectorConfig(
                    multiline=True,
                )
            ),
            vol.Required("points", default=10): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=1000, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("time_category", default="anytime"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=time_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("due_days", default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=day_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            ),
            vol.Required("requires_approval", default=True): bool,
            vol.Required("daily_limit", default=1): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("completion_percentage_per_month", default=100): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional("completion_sound", default=DEFAULT_COMPLETION_SOUND): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=sound, label=sound.title() if sound != "none" else "No Sound")
                        for sound in COMPLETION_SOUND_OPTIONS
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }

        if child_options:
            schema_dict[vol.Optional("assigned_to", default=[])] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=child_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            )

        return self.async_show_form(
            step_id="add_chores_bulk",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "description": "Enter chore names, one per line or comma-separated",
            },
        )

    async def async_step_edit_chore(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit a chore."""
        chore = self.coordinator.get_chore(self._selected_chore_id)
        if not chore:
            return await self.async_step_manage_chores()

        errors: dict[str, str] = {}
        children = self.coordinator.storage.get_children()

        if user_input is not None:
            action = user_input.get("action")
            if action == "delete":
                await self.coordinator.async_remove_chore(chore.id)
                return await self.async_step_manage_chores()
            elif action == "save":
                chore.name = user_input.get("name", chore.name)
                chore.description = user_input.get("description", chore.description)
                chore.points = int(user_input.get("points", chore.points))
                chore.due_days = user_input.get("due_days", chore.due_days)
                chore.assigned_to = user_input.get("assigned_to", chore.assigned_to)
                chore.requires_approval = user_input.get("requires_approval", chore.requires_approval)
                chore.time_category = user_input.get("time_category", chore.time_category)
                chore.daily_limit = int(user_input.get("daily_limit", chore.daily_limit))
                chore.completion_percentage_per_month = int(user_input.get("completion_percentage_per_month", getattr(chore, 'completion_percentage_per_month', 100)))
                chore.completion_sound = user_input.get("completion_sound", chore.completion_sound)
                await self.coordinator.async_update_chore(chore)
                return await self.async_step_manage_chores()

        child_options = [
            selector.SelectOptionDict(value=c.id, label=c.name)
            for c in children
        ]

        day_options = [
            selector.SelectOptionDict(value=day, label=day.title())
            for day in DAYS_OF_WEEK
        ]

        time_options = [
            selector.SelectOptionDict(value=tc, label=tc.title())
            for tc in TIME_CATEGORIES
        ]

        schema_dict = {
            vol.Required("name", default=chore.name): str,
            vol.Optional("description", default=chore.description): str,
            vol.Required("points", default=chore.points): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=1000, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("time_category", default=chore.time_category): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=time_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("due_days", default=chore.due_days): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=day_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            ),
            vol.Required("requires_approval", default=chore.requires_approval): bool,
            vol.Required("daily_limit", default=chore.daily_limit): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("completion_percentage_per_month", default=getattr(chore, 'completion_percentage_per_month', 100)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional("completion_sound", default=getattr(chore, 'completion_sound', DEFAULT_COMPLETION_SOUND)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=sound, label=sound.title() if sound != "none" else "No Sound")
                        for sound in COMPLETION_SOUND_OPTIONS
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("action", default="save"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="save", label="Save Changes"),
                        selector.SelectOptionDict(value="delete", label="Delete Chore"),
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }

        if child_options:
            schema_dict[vol.Optional("assigned_to", default=chore.assigned_to)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=child_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            )

        return self.async_show_form(
            step_id="edit_chore",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={"chore_name": chore.name},
        )

    # ==================== REWARDS MANAGEMENT ====================

    async def async_step_manage_rewards(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage rewards menu."""
        rewards = self.coordinator.storage.get_rewards()
        menu_options = {"add_reward": "Add New Reward"}

        for reward in rewards:
            menu_options[f"edit_reward_{reward.id}"] = f"Edit: {reward.name} ({reward.cost} pts)"

        menu_options["init"] = "Back to Main Menu"

        return self.async_show_menu(
            step_id="manage_rewards",
            menu_options=menu_options,
        )

    async def async_step_add_reward(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add a new reward."""
        errors: dict[str, str] = {}
        children = self.coordinator.storage.get_children()

        if user_input is not None:
            name = user_input.get("name", "").strip()
            if not name:
                errors["name"] = "name_required"
            else:
                await self.coordinator.async_add_reward(
                    name=name,
                    cost=int(user_input.get("cost", 50)),
                    description=user_input.get("description", ""),
                    icon=user_input.get("icon", "mdi:gift"),
                    assigned_to=user_input.get("assigned_to", []),
                    is_jackpot=user_input.get("is_jackpot", False),
                    override_point_value=user_input.get("override_point_value", False),
                    days_to_goal=int(user_input.get("days_to_goal", 30)),
                )
                return await self.async_step_manage_rewards()

        child_options = [
            selector.SelectOptionDict(value=c.id, label=c.name)
            for c in children
        ]

        schema_dict = {
            vol.Required("name"): str,
            vol.Optional("description", default=""): str,
            vol.Optional("icon", default="mdi:gift"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=icon, label=icon.replace("mdi:", "").replace("-", " ").title())
                        for icon in REWARD_ICON_OPTIONS
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("is_jackpot", default=False): selector.BooleanSelector(),
            vol.Required("days_to_goal", default=30): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=365, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional("override_point_value", default=False): selector.BooleanSelector(),
            vol.Optional("cost", default=50): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10000, mode=selector.NumberSelectorMode.BOX)
            ),
        }

        if child_options:
            schema_dict[vol.Optional("assigned_to", default=[])] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=child_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            )

        return self.async_show_form(
            step_id="add_reward",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_edit_reward(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit a reward."""
        reward = self.coordinator.get_reward(self._selected_reward_id)
        if not reward:
            return await self.async_step_manage_rewards()

        errors: dict[str, str] = {}
        children = self.coordinator.storage.get_children()

        if user_input is not None:
            action = user_input.get("action")
            if action == "delete":
                await self.coordinator.async_remove_reward(reward.id)
                return await self.async_step_manage_rewards()
            elif action == "save":
                reward.name = user_input.get("name", reward.name)
                reward.description = user_input.get("description", reward.description)
                reward.cost = int(user_input.get("cost", reward.cost))
                reward.icon = user_input.get("icon", reward.icon)
                reward.assigned_to = user_input.get("assigned_to", reward.assigned_to)
                reward.is_jackpot = user_input.get("is_jackpot", reward.is_jackpot)
                reward.override_point_value = user_input.get("override_point_value", getattr(reward, 'override_point_value', False))
                reward.days_to_goal = int(user_input.get("days_to_goal", getattr(reward, 'days_to_goal', 30)))
                await self.coordinator.async_update_reward(reward)
                return await self.async_step_manage_rewards()

        child_options = [
            selector.SelectOptionDict(value=c.id, label=c.name)
            for c in children
        ]

        schema_dict = {
            vol.Required("name", default=reward.name): str,
            vol.Optional("description", default=reward.description): str,
            vol.Optional("icon", default=reward.icon): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=icon, label=icon.replace("mdi:", "").replace("-", " ").title())
                        for icon in REWARD_ICON_OPTIONS
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("is_jackpot", default=getattr(reward, 'is_jackpot', False)): selector.BooleanSelector(),
            vol.Required("days_to_goal", default=getattr(reward, 'days_to_goal', 30)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=365, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Optional("override_point_value", default=getattr(reward, 'override_point_value', False)): selector.BooleanSelector(),
            vol.Optional("cost", default=reward.cost): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10000, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("action", default="save"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="save", label="Save Changes"),
                        selector.SelectOptionDict(value="delete", label="Delete Reward"),
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }

        if child_options:
            schema_dict[vol.Optional("assigned_to", default=reward.assigned_to)] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=child_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            )

        return self.async_show_form(
            step_id="edit_reward",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={"reward_name": reward.name},
        )

    # ==================== SETTINGS ====================

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure settings."""
        if user_input is not None:
            await self.coordinator.async_set_points_settings(
                name=user_input.get("points_name", DEFAULT_POINTS_NAME),
                icon=user_input.get("points_icon", DEFAULT_POINTS_ICON),
            )
            return await self.async_step_init()

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "points_name",
                        default=self.coordinator.storage.get_points_name(),
                    ): str,
                    vol.Required(
                        "points_icon",
                        default=self.coordinator.storage.get_points_icon(),
                    ): selector.IconSelector(),
                }
            ),
        )

    # ==================== DYNAMIC STEP ROUTING ====================

    def __getattr__(self, name: str):
        """Handle dynamic step routing for edit_child_*, edit_chore_*, etc."""
        if name.startswith("async_step_edit_child_"):
            child_id = name.replace("async_step_edit_child_", "")
            self._selected_child_id = child_id
            return self.async_step_edit_child
        elif name.startswith("async_step_edit_chore_"):
            chore_id = name.replace("async_step_edit_chore_", "")
            self._selected_chore_id = chore_id
            return self.async_step_edit_chore
        elif name.startswith("async_step_edit_reward_"):
            reward_id = name.replace("async_step_edit_reward_", "")
            self._selected_reward_id = reward_id
            return self.async_step_edit_reward
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
