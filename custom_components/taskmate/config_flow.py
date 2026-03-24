"""Config flow for TaskMate integration."""
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
    FIRST_OCCURRENCE_MODES,
    RECURRENCE_LABELS,
    RECURRENCE_OPTIONS,
    REWARD_ICON_OPTIONS,
    SCHEDULE_MODES,
    TIME_CATEGORIES,
    TIME_CATEGORY_ICONS,
)

_LOGGER = logging.getLogger(__name__)


class TaskMateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TaskMate."""

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
                title="TaskMate",
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
                "title": "Welcome to TaskMate!",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> TaskMateOptionsFlow:
        """Create the options flow."""
        return TaskMateOptionsFlow(config_entry)


class TaskMateOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for TaskMate."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._selected_child_id: str | None = None
        self._selected_chore_id: str | None = None
        self._selected_reward_id: str | None = None
        self._chore_step1_data: dict | None = None  # Holds step 1 data while user completes step 2

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
        """Add a new chore — Step 1: core fields + schedule mode selection."""
        errors: dict[str, str] = {}
        children = self.coordinator.storage.get_children()

        if user_input is not None:
            name = user_input.get("name", "").strip()
            if not name:
                errors["name"] = "name_required"
            else:
                # Store step 1 data and proceed to scheduling step
                self._chore_step1_data = user_input
                schedule_mode = user_input.get("schedule_mode", "specific_days")
                if schedule_mode == "specific_days":
                    return await self.async_step_chore_schedule_specific()
                else:
                    return await self.async_step_chore_schedule_recurring()

        child_options = [
            selector.SelectOptionDict(value=c.id, label=c.name)
            for c in children
        ]
        time_options = [
            selector.SelectOptionDict(value=tc, label=tc.title())
            for tc in TIME_CATEGORIES
        ]
        schedule_mode_options = [
            selector.SelectOptionDict(value="specific_days", label="Specific days of the week"),
            selector.SelectOptionDict(value="recurring", label="Recurring (every N days/weeks/months)"),
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
            vol.Required("schedule_mode", default="specific_days"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=schedule_mode_options,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required("requires_approval", default=True): bool,
            vol.Required("daily_limit", default=1): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, mode=selector.NumberSelectorMode.BOX)
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

    async def async_step_chore_schedule_specific(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add chore — Step 2a: specific days scheduling."""
        if user_input is not None:
            s1 = self._chore_step1_data or {}
            await self.coordinator.async_add_chore(
                name=s1.get("name", "").strip(),
                points=int(s1.get("points", 10)),
                description=s1.get("description", ""),
                assigned_to=s1.get("assigned_to", []),
                requires_approval=s1.get("requires_approval", True),
                time_category=s1.get("time_category", "anytime"),
                daily_limit=int(s1.get("daily_limit", 1)),
                completion_sound=s1.get("completion_sound", DEFAULT_COMPLETION_SOUND),
                schedule_mode="specific_days",
                due_days=user_input.get("due_days", []),
            )
            self._chore_step1_data = None
            return await self.async_step_manage_chores()

        day_options = [
            selector.SelectOptionDict(value=day, label=day.title())
            for day in DAYS_OF_WEEK
        ]
        return self.async_show_form(
            step_id="chore_schedule_specific",
            data_schema=vol.Schema({
                vol.Optional("due_days", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=day_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        multiple=True,
                    )
                ),
            }),
        )

    async def async_step_chore_schedule_recurring(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add chore — Step 2b: recurring schedule."""
        if user_input is not None:
            s1 = self._chore_step1_data or {}
            recurrence = user_input.get("recurrence", "weekly")
            # Only store recurrence_day if relevant recurrence type
            recurrence_day = ""
            if recurrence in ("weekly", "every_2_weeks"):
                recurrence_day = user_input.get("recurrence_day", "")
            # Only store recurrence_start if every_2_days
            recurrence_start = ""
            if recurrence == "every_2_days":
                recurrence_start = user_input.get("recurrence_start", "")
            # Only store first_occurrence_mode if an anchor applies
            first_occurrence_mode = user_input.get("first_occurrence_mode", "available_immediately")

            await self.coordinator.async_add_chore(
                name=s1.get("name", "").strip(),
                points=int(s1.get("points", 10)),
                description=s1.get("description", ""),
                assigned_to=s1.get("assigned_to", []),
                requires_approval=s1.get("requires_approval", True),
                time_category=s1.get("time_category", "anytime"),
                daily_limit=int(s1.get("daily_limit", 1)),
                completion_sound=s1.get("completion_sound", DEFAULT_COMPLETION_SOUND),
                schedule_mode="recurring",
                recurrence=recurrence,
                recurrence_day=recurrence_day,
                recurrence_start=recurrence_start,
                first_occurrence_mode=first_occurrence_mode,
            )
            self._chore_step1_data = None
            return await self.async_step_manage_chores()

        recurrence_options = [
            selector.SelectOptionDict(value=k, label=v)
            for k, v in RECURRENCE_LABELS.items()
        ]
        day_options = [
            selector.SelectOptionDict(value=day, label=day.title())
            for day in DAYS_OF_WEEK
        ]
        first_occurrence_options = [
            selector.SelectOptionDict(value="available_immediately", label="Available immediately"),
            selector.SelectOptionDict(value="wait_for_first_occurrence", label="Wait for first scheduled occurrence"),
        ]

        return self.async_show_form(
            step_id="chore_schedule_recurring",
            data_schema=vol.Schema({
                vol.Required("recurrence", default="weekly"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=recurrence_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("recurrence_day", default=""): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value="", label="Any day")] + day_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("recurrence_start", default=""): selector.TextSelector(
                    selector.TextSelectorConfig()
                ),
                vol.Required("first_occurrence_mode", default="available_immediately"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=first_occurrence_options,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }),
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
                        schedule_mode="specific_days",
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
        """Edit an existing chore — Step 1: core fields + schedule mode."""
        errors: dict[str, str] = {}
        chore_id = self._selected_chore_id
        chore = self.coordinator.get_chore(chore_id)
        if not chore:
            return await self.async_step_manage_chores()

        children = self.coordinator.storage.get_children()

        if user_input is not None:
            action = user_input.get("action", "save")
            if action == "delete":
                await self.coordinator.async_delete_chore(chore_id)
                return await self.async_step_manage_chores()

            name = user_input.get("name", "").strip()
            if not name:
                errors["name"] = "name_required"
            else:
                self._chore_step1_data = {**user_input, "_editing": True, "_chore_id": chore_id}
                schedule_mode = user_input.get("schedule_mode", "specific_days")
                if schedule_mode == "specific_days":
                    return await self.async_step_edit_chore_schedule_specific()
                else:
                    return await self.async_step_edit_chore_schedule_recurring()

        child_options = [
            selector.SelectOptionDict(value=c.id, label=c.name)
            for c in children
        ]
        time_options = [
            selector.SelectOptionDict(value=tc, label=tc.title())
            for tc in TIME_CATEGORIES
        ]
        schedule_mode_options = [
            selector.SelectOptionDict(value="specific_days", label="Specific days of the week"),
            selector.SelectOptionDict(value="recurring", label="Recurring (every N days/weeks/months)"),
        ]
        action_options = [
            selector.SelectOptionDict(value="save", label="Save Changes"),
            selector.SelectOptionDict(value="delete", label="Delete This Chore"),
        ]

        current_assigned = chore.assigned_to if isinstance(chore.assigned_to, list) else []
        current_schedule_mode = getattr(chore, 'schedule_mode', 'specific_days')

        schema_dict = {
            vol.Required("name", default=chore.name): str,
            vol.Optional("description", default=chore.description or ""): str,
            vol.Required("points", default=chore.points): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=1000, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("time_category", default=chore.time_category): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=time_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required("schedule_mode", default=current_schedule_mode): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=schedule_mode_options,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
            vol.Required("requires_approval", default=chore.requires_approval): bool,
            vol.Required("daily_limit", default=chore.daily_limit): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10, mode=selector.NumberSelectorMode.BOX)
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
                    options=action_options,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }
        if child_options:
            schema_dict[vol.Optional("assigned_to", default=current_assigned)] = selector.SelectSelector(
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

    async def async_step_edit_chore_schedule_specific(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit chore — Step 2a: specific days."""
        s1 = self._chore_step1_data or {}
        chore_id = s1.get("_chore_id") or self._selected_chore_id
        chore = self.coordinator.get_chore(chore_id)
        if not chore:
            return await self.async_step_manage_chores()

        if user_input is not None:
            chore.name = s1.get("name", chore.name).strip()
            chore.points = int(s1.get("points", chore.points))
            chore.description = s1.get("description", chore.description)
            chore.assigned_to = s1.get("assigned_to", chore.assigned_to)
            chore.requires_approval = s1.get("requires_approval", chore.requires_approval)
            chore.time_category = s1.get("time_category", chore.time_category)
            chore.daily_limit = int(s1.get("daily_limit", chore.daily_limit))
            chore.completion_sound = s1.get("completion_sound", getattr(chore, 'completion_sound', DEFAULT_COMPLETION_SOUND))
            chore.schedule_mode = "specific_days"
            chore.due_days = user_input.get("due_days", [])
            # Clear recurring fields
            chore.recurrence = "weekly"
            chore.recurrence_day = ""
            chore.recurrence_start = ""
            chore.first_occurrence_mode = "available_immediately"
            await self.coordinator.async_update_chore(chore)
            self._chore_step1_data = None
            return await self.async_step_manage_chores()

        day_options = [
            selector.SelectOptionDict(value=day, label=day.title())
            for day in DAYS_OF_WEEK
        ]
        return self.async_show_form(
            step_id="edit_chore_schedule_specific",
            data_schema=vol.Schema({
                vol.Optional("due_days", default=chore.due_days or []): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=day_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        multiple=True,
                    )
                ),
            }),
            description_placeholders={"chore_name": chore.name},
        )

    async def async_step_edit_chore_schedule_recurring(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit chore — Step 2b: recurring schedule."""
        s1 = self._chore_step1_data or {}
        chore_id = s1.get("_chore_id") or self._selected_chore_id
        chore = self.coordinator.get_chore(chore_id)
        if not chore:
            return await self.async_step_manage_chores()

        if user_input is not None:
            chore.name = s1.get("name", chore.name).strip()
            chore.points = int(s1.get("points", chore.points))
            chore.description = s1.get("description", chore.description)
            chore.assigned_to = s1.get("assigned_to", chore.assigned_to)
            chore.requires_approval = s1.get("requires_approval", chore.requires_approval)
            chore.time_category = s1.get("time_category", chore.time_category)
            chore.daily_limit = int(s1.get("daily_limit", chore.daily_limit))
            chore.completion_sound = s1.get("completion_sound", getattr(chore, 'completion_sound', DEFAULT_COMPLETION_SOUND))
            chore.schedule_mode = "recurring"
            chore.due_days = []
            recurrence = user_input.get("recurrence", "weekly")
            chore.recurrence = recurrence
            chore.recurrence_day = user_input.get("recurrence_day", "") if recurrence in ("weekly", "every_2_weeks") else ""
            chore.recurrence_start = user_input.get("recurrence_start", "") if recurrence == "every_2_days" else ""
            chore.first_occurrence_mode = user_input.get("first_occurrence_mode", "available_immediately")
            await self.coordinator.async_update_chore(chore)
            self._chore_step1_data = None
            return await self.async_step_manage_chores()

        recurrence_options = [
            selector.SelectOptionDict(value=k, label=v)
            for k, v in RECURRENCE_LABELS.items()
        ]
        day_options = [
            selector.SelectOptionDict(value=day, label=day.title())
            for day in DAYS_OF_WEEK
        ]
        first_occurrence_options = [
            selector.SelectOptionDict(value="available_immediately", label="Available immediately"),
            selector.SelectOptionDict(value="wait_for_first_occurrence", label="Wait for first scheduled occurrence"),
        ]
        current_recurrence = getattr(chore, 'recurrence', 'weekly')

        return self.async_show_form(
            step_id="edit_chore_schedule_recurring",
            data_schema=vol.Schema({
                vol.Required("recurrence", default=current_recurrence): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=recurrence_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("recurrence_day", default=getattr(chore, 'recurrence_day', '')): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[selector.SelectOptionDict(value="", label="Any day")] + day_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("recurrence_start", default=getattr(chore, 'recurrence_start', '')): selector.TextSelector(
                    selector.TextSelectorConfig()
                ),
                vol.Required("first_occurrence_mode", default=getattr(chore, 'first_occurrence_mode', 'available_immediately')): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=first_occurrence_options,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }),
            description_placeholders={"chore_name": chore.name},
        )


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
            vol.Required("cost", default=50): selector.NumberSelector(
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
            await self.coordinator.async_set_setting(
                "streak_reset_mode",
                user_input.get("streak_reset_mode", "reset"),
            )
            await self.coordinator.async_set_setting(
                "history_days",
                str(int(float(user_input.get("history_days", 90)))),
            )
            await self.coordinator.async_set_setting(
                "weekend_multiplier",
                str(float(user_input.get("weekend_multiplier", 2.0))),
            )
            await self.coordinator.async_set_setting(
                "streak_milestones_enabled",
                "true" if user_input.get("streak_milestones_enabled", True) else "false",
            )
            milestone_input = user_input.get(
                "streak_milestones", self.coordinator.DEFAULT_STREAK_MILESTONES
            ).strip()
            try:
                from .coordinator import TaskMateCoordinator
                TaskMateCoordinator.parse_milestone_setting(milestone_input)
            except ValueError as err:
                return self.async_show_form(
                    step_id="settings",
                    errors={"streak_milestones": "invalid_milestone_format"},
                    description_placeholders={"error": str(err)},
                    data_schema=vol.Schema({}),
                )
            await self.coordinator.async_set_setting(
                "streak_milestones",
                milestone_input,
            )
            await self.coordinator.async_set_setting(
                "perfect_week_enabled",
                "true" if user_input.get("perfect_week_enabled", True) else "false",
            )
            await self.coordinator.async_set_setting(
                "perfect_week_bonus",
                str(int(float(user_input.get("perfect_week_bonus", 50)))),
            )
            await self.coordinator.async_set_setting(
                "notify_service",
                user_input.get("notify_service", "").strip(),
            )
            return await self.async_step_init()

        current_streak_mode = self.coordinator.storage.get_setting("streak_reset_mode", "reset")
        try:
            current_history_days = float(self.coordinator.storage.get_setting("history_days", "90"))
        except (ValueError, TypeError):
            current_history_days = 90.0
        try:
            current_weekend_multiplier = float(self.coordinator.storage.get_setting("weekend_multiplier", "2.0"))
        except (ValueError, TypeError):
            current_weekend_multiplier = 2.0
        current_streak_milestones = self.coordinator.storage.get_setting("streak_milestones_enabled", "true") == "true"
        current_milestone_config = self.coordinator.storage.get_setting(
            "streak_milestones", self.coordinator.DEFAULT_STREAK_MILESTONES
        )
        current_perfect_week = self.coordinator.storage.get_setting("perfect_week_enabled", "true") == "true"
        try:
            current_perfect_week_bonus = float(self.coordinator.storage.get_setting("perfect_week_bonus", "50"))
        except (ValueError, TypeError):
            current_perfect_week_bonus = 50.0
        current_notify_service = self.coordinator.storage.get_setting("notify_service", "")

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
                    vol.Required(
                        "streak_reset_mode",
                        default=current_streak_mode,
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value="reset", label="Reset — streak goes to 0 on missed day"),
                                selector.SelectOptionDict(value="pause", label="Pause — streak preserved until next completion"),
                            ],
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                    vol.Required(
                        "history_days",
                        default=current_history_days,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=30,
                            max=365,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        "weekend_multiplier",
                        default=current_weekend_multiplier,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1.0,
                            max=5.0,
                            step=0.5,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        "streak_milestones_enabled",
                        default=current_streak_milestones,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        "streak_milestones",
                        default=current_milestone_config,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=False)
                    ),
                    vol.Required(
                        "perfect_week_enabled",
                        default=current_perfect_week,
                    ): selector.BooleanSelector(),
                    vol.Required(
                        "perfect_week_bonus",
                        default=current_perfect_week_bonus,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=10,
                            max=500,
                            step=5,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        "notify_service",
                        default=current_notify_service,
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=False)
                    ),
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
