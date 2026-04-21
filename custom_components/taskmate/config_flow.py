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
    ASSIGNMENT_MODES,
    AVATAR_OPTIONS,
    COMPLETION_SOUND_OPTIONS,
    DAYS_OF_WEEK,
    DEFAULT_CALENDAR_PROJECTION_DAYS,
    DEFAULT_CLAIM_ALLOWANCE_MINUTES,
    DEFAULT_COMPLETION_SOUND,
    DEFAULT_POINTS_ICON,
    DEFAULT_POINTS_NAME,
    DOMAIN,
    MAX_CALENDAR_PROJECTION_DAYS,
    MIN_CALENDAR_PROJECTION_DAYS,
    RECURRENCE_OPTIONS,
    REWARD_ICON_OPTIONS,
    TIME_CATEGORIES,
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
        self._edited_chore = None  # Holds the chore object during edit flow across steps
        self._translations: dict | None = None

    @property
    def coordinator(self):
        """Get the coordinator, or raise a clear error if not yet registered."""
        entry_id = getattr(self.config_entry, "entry_id", None)
        domain_data = self.hass.data.get(DOMAIN) if self.hass is not None else None
        if not entry_id or not domain_data or entry_id not in domain_data:
            raise RuntimeError(
                "TaskMate coordinator is not available for this config entry yet"
            )
        return domain_data[entry_id]

    async def _async_get_user_language(self) -> str:
        """Get the current user's language from their HA profile."""
        try:
            user_id = self.context.get("user_id") if self.context else None
            if user_id:
                # HA stores user preferences in the frontend storage
                store = self.hass.data.get("frontend_storage")
                if store:
                    data = await store.async_load() if hasattr(store, 'async_load') else None
                    if data and user_id in data:
                        lang = data[user_id].get("language", {}).get("language")
                        if lang:
                            return lang
                # Try the frontend user data directly
                frontend_data = self.hass.data.get("frontend")
                if frontend_data and hasattr(frontend_data, 'async_get_user_data'):
                    user_data = await frontend_data.async_get_user_data(user_id)
                    if user_data and user_data.get("language"):
                        return user_data["language"]
        except (AttributeError, KeyError, TypeError) as err:
            _LOGGER.debug("TaskMate i18n: could not resolve user language: %s", err)
        # Fall back to system language
        return getattr(self.hass.config, 'language', None) or "en"

    async def _async_load_translations(self) -> None:
        """Load translations for the current user's language."""
        if self._translations is not None:
            return
        import json
        from pathlib import Path

        lang = await self._async_get_user_language()
        _LOGGER.debug("TaskMate i18n: detected language=%s", lang)

        # First try HA's translation system
        try:
            from homeassistant.helpers.translation import async_get_translations
            self._translations = await async_get_translations(
                self.hass, lang, "options", DOMAIN
            )
            if self._translations:
                _LOGGER.debug("TaskMate i18n: loaded %d keys via HA for lang=%s", len(self._translations), lang)
                return
        except (ImportError, AttributeError, RuntimeError) as e:
            _LOGGER.debug("TaskMate i18n: HA translation system unavailable: %s", e)

        # Fallback: load translation file directly
        translations_dir = Path(__file__).parent / "translations"
        for candidate in [lang, lang.split("-")[0], "en"]:
            path = translations_dir / f"{candidate}.json"
            if path.exists():
                try:
                    text = await self.hass.async_add_executor_job(path.read_text, "utf-8")
                    self._translations = json.loads(text)
                    _LOGGER.debug("TaskMate i18n: loaded file %s", candidate)
                    return
                except (OSError, ValueError) as err:
                    _LOGGER.debug("TaskMate i18n: failed to load %s: %s", candidate, err)
                    continue
        self._translations = {}

    def _t(self, key: str, default: str = "") -> str:
        """Look up a translation key. Supports both HA flat keys and dotted nested keys."""
        if not self._translations:
            return default
        # HA's async_get_translations returns flat keys like:
        # "component.taskmate.options.step.manage_children.menu_options.add_child"
        ha_key = f"component.{DOMAIN}.{key}"
        if ha_key in self._translations:
            return self._translations[ha_key]
        # Fallback: navigate dotted key through nested dict (manual file load)
        parts = key.split(".")
        obj = self._translations
        for part in parts:
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return default
        return obj if isinstance(obj, str) else default

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options - main menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "manage_children",
                "manage_chores",
                "manage_rewards",
                "settings",
            ],
        )

    # ==================== CHILDREN MANAGEMENT ====================

    async def async_step_manage_children(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage children menu."""
        await self._async_load_translations()
        children = self.coordinator.storage.get_children()
        _m = lambda key, default: self._t(f"options.step.manage_children.menu_options.{key}", default)
        menu_options = {"add_child": _m("add_child", "Add New Child")}

        for child in children:
            menu_options[f"edit_child_{child.id}"] = f"{child.name}"

        menu_options["init"] = _m("init", "Back to Main Menu")

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
                            options=["save", "delete"],
                            translation_key="child_action",
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
        await self._async_load_translations()
        chores = self.coordinator.storage.get_chores()
        _m = lambda key, default: self._t(f"options.step.manage_chores.menu_options.{key}", default)
        menu_options = {
            "add_chore": _m("add_chore", "Add Single Chore"),
            "add_chores_bulk": _m("add_chores_bulk", "Add Multiple Chores"),
        }

        for chore in chores:
            time_label = f" [{chore.time_category}]" if chore.time_category != "anytime" else ""
            disabled_label = " (disabled)" if (not getattr(chore, 'enabled', True) or getattr(chore, 'disabled_for', [])) else ""
            menu_options[f"edit_chore_{chore.id}"] = f"{chore.name} ({chore.points} pts){time_label}{disabled_label}"

        menu_options["init"] = _m("init", "Back to Main Menu")

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
                elif schedule_mode == "one_shot":
                    return await self.async_step_chore_schedule_one_shot()
                else:
                    return await self.async_step_chore_schedule_recurring()

        child_options = [
            selector.SelectOptionDict(value=c.id, label=c.name)
            for c in children
        ]
        schema_dict = {
            vol.Required("name"): str,
            vol.Optional("description", default=""): str,
            vol.Required("points", default=10): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=1000, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("time_category", default="anytime"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(TIME_CATEGORIES),
                    translation_key="time_category",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("claim_allowance_minutes", default=DEFAULT_CLAIM_ALLOWANCE_MINUTES): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=720, step=5, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min")
            ),
            vol.Required("schedule_mode", default="specific_days"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["specific_days", "recurring", "one_shot"],
                    translation_key="schedule_mode",
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
            vol.Optional("visibility_entity"): selector.EntitySelector(
                selector.EntitySelectorConfig()
            ),
            vol.Optional("assignment_mode", default="everyone"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(ASSIGNMENT_MODES),
                    translation_key="assignment_mode",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("assignment_rotation_anchor", default=""): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.DATE)
            ),
            vol.Optional("publish_calendar_entities", default=[]): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="calendar", multiple=True)
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
            last_step=False,
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
                claim_allowance_minutes=int(s1.get("claim_allowance_minutes", DEFAULT_CLAIM_ALLOWANCE_MINUTES) or 0),
                daily_limit=int(s1.get("daily_limit", 1)),
                completion_sound=s1.get("completion_sound", DEFAULT_COMPLETION_SOUND),
                schedule_mode="specific_days",
                due_days=user_input.get("due_days", []),
                visibility_entity=s1.get("visibility_entity") or "",
                assignment_mode=s1.get("assignment_mode", "everyone"),
                assignment_rotation_anchor=s1.get("assignment_rotation_anchor", "") or "",
                publish_calendar_entities=list(s1.get("publish_calendar_entities") or []),
            )
            self._chore_step1_data = None
            return await self.async_step_manage_chores()

        return self.async_show_form(
            step_id="chore_schedule_specific",
            data_schema=vol.Schema({
                vol.Optional("due_days", default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(DAYS_OF_WEEK),
                        translation_key="due_days_option",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        multiple=True,
                    )
                ),
            }),
        )

    async def async_step_chore_schedule_one_shot(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Add chore — one-shot (no schedule config needed)."""
        s1 = self._chore_step1_data or {}
        await self.coordinator.async_add_chore(
            name=s1.get("name", "").strip(),
            points=int(s1.get("points", 10)),
            description=s1.get("description", ""),
            assigned_to=s1.get("assigned_to", []),
            requires_approval=s1.get("requires_approval", True),
            time_category=s1.get("time_category", "anytime"),
            claim_allowance_minutes=int(s1.get("claim_allowance_minutes", DEFAULT_CLAIM_ALLOWANCE_MINUTES) or 0),
            daily_limit=1,
            completion_sound=s1.get("completion_sound", DEFAULT_COMPLETION_SOUND),
            schedule_mode="one_shot",
            visibility_entity=s1.get("visibility_entity") or "",
            assignment_mode=s1.get("assignment_mode", "everyone"),
            assignment_rotation_anchor=s1.get("assignment_rotation_anchor", "") or "",
            publish_calendar_entities=list(s1.get("publish_calendar_entities") or []),
        )
        self._chore_step1_data = None
        return await self.async_step_manage_chores()

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
                if recurrence_day == "any_day":
                    recurrence_day = ""
            # Only store recurrence_start if every_2_days
            recurrence_start = ""
            if recurrence == "every_2_days":
                recurrence_start = user_input.get("recurrence_start", "") or ""
            # Only store first_occurrence_mode if an anchor applies
            first_occurrence_mode = user_input.get("first_occurrence_mode", "available_immediately")

            await self.coordinator.async_add_chore(
                name=s1.get("name", "").strip(),
                points=int(s1.get("points", 10)),
                description=s1.get("description", ""),
                assigned_to=s1.get("assigned_to", []),
                requires_approval=s1.get("requires_approval", True),
                time_category=s1.get("time_category", "anytime"),
                claim_allowance_minutes=int(s1.get("claim_allowance_minutes", DEFAULT_CLAIM_ALLOWANCE_MINUTES) or 0),
                daily_limit=int(s1.get("daily_limit", 1)),
                completion_sound=s1.get("completion_sound", DEFAULT_COMPLETION_SOUND),
                schedule_mode="recurring",
                recurrence=recurrence,
                recurrence_day=recurrence_day,
                recurrence_start=recurrence_start,
                first_occurrence_mode=first_occurrence_mode,
                visibility_entity=s1.get("visibility_entity") or "",
                assignment_mode=s1.get("assignment_mode", "everyone"),
                assignment_rotation_anchor=s1.get("assignment_rotation_anchor", "") or "",
                publish_calendar_entities=list(s1.get("publish_calendar_entities") or []),
            )
            self._chore_step1_data = None
            return await self.async_step_manage_chores()

        return self.async_show_form(
            step_id="chore_schedule_recurring",
            data_schema=vol.Schema({
                vol.Required("recurrence", default="weekly"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(RECURRENCE_OPTIONS),
                        translation_key="recurrence",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("recurrence_day", default="any_day"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["any_day"] + list(DAYS_OF_WEEK),
                        translation_key="recurrence_day_option",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("recurrence_start", default=""): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.DATE)
                ),
                vol.Required("first_occurrence_mode", default="available_immediately"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["available_immediately", "wait_for_first_occurrence"],
                        translation_key="first_occurrence_mode",
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
                    await self.coordinator.async_add_chores_bulk(
                        chore_names=chore_names,
                        points=int(user_input.get("points", 10)),
                        due_days=user_input.get("due_days", []),
                        assigned_to=user_input.get("assigned_to", []),
                        requires_approval=user_input.get("requires_approval", True),
                        time_category=user_input.get("time_category", "anytime"),
                        claim_allowance_minutes=int(user_input.get("claim_allowance_minutes", DEFAULT_CLAIM_ALLOWANCE_MINUTES) or 0),
                        daily_limit=int(user_input.get("daily_limit", 1)),
                        schedule_mode="specific_days",
                        completion_sound=user_input.get("completion_sound", DEFAULT_COMPLETION_SOUND),
                        visibility_entity=user_input.get("visibility_entity") or "",
                    )
                    return await self.async_step_manage_chores()

        child_options = [
            selector.SelectOptionDict(value=c.id, label=c.name)
            for c in children
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
                    options=list(TIME_CATEGORIES),
                    translation_key="time_category",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("claim_allowance_minutes", default=DEFAULT_CLAIM_ALLOWANCE_MINUTES): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=720, step=5, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min")
            ),
            vol.Optional("due_days", default=[]): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(DAYS_OF_WEEK),
                    translation_key="due_days_option",
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
            vol.Optional("visibility_entity"): selector.EntitySelector(
                selector.EntitySelectorConfig()
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

    @staticmethod
    def _get_chore_action_options(chore) -> list[str]:
        """Build the action options list for the chore edit form."""
        is_one_shot = getattr(chore, 'schedule_mode', 'specific_days') == 'one_shot'
        is_disabled = not getattr(chore, 'enabled', True) or getattr(chore, 'disabled_for', [])

        if is_one_shot:
            if is_disabled:
                return ["save", "re_enable", "delete"]
            else:
                return ["save", "disable", "delete"]
        elif is_disabled:
            return ["save", "re_enable", "delete"]
        else:
            return ["save", "delete"]

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
                await self.coordinator.async_remove_chore(chore_id)
                return await self.async_step_manage_chores()
            if action == "re_enable":
                chore.enabled = True
                chore.disabled_for = []
                if getattr(chore, 'schedule_mode', 'specific_days') == 'one_shot':
                    from homeassistant.util import dt as dt_util
                    chore.created_date = dt_util.as_local(dt_util.now()).date().isoformat()
                await self.coordinator.async_update_chore(chore)
                return await self.async_step_manage_chores()
            if action == "disable":
                chore.enabled = False
                await self.coordinator.async_update_chore(chore)
                return await self.async_step_manage_chores()

            name = user_input.get("name", "").strip()
            if not name:
                errors["name"] = "name_required"

            # Validate visibility: if entity is set, operator and state are required
            vis_entity = user_input.get("visibility_entity") or ""
            vis_operator = user_input.get("visibility_operator", "none")
            vis_state = user_input.get("visibility_state", "")

            # If operator is "none", treat as no visibility filter regardless of entity
            if not vis_operator or vis_operator == "none":
                vis_entity = ""

            if vis_entity:
                if not vis_state.strip():
                    errors["visibility_state"] = "state_required"

            if not errors:
                # Update the chore object with all Step 1 fields
                chore.name = name
                chore.points = int(user_input.get("points", chore.points))
                chore.description = user_input.get("description", chore.description)
                chore.assigned_to = user_input.get("assigned_to", chore.assigned_to)
                chore.requires_approval = user_input.get("requires_approval", chore.requires_approval)
                chore.time_category = user_input.get("time_category", chore.time_category)
                chore.claim_allowance_minutes = max(0, int(user_input.get("claim_allowance_minutes", getattr(chore, "claim_allowance_minutes", 0)) or 0))
                chore.daily_limit = int(user_input.get("daily_limit", chore.daily_limit))
                chore.completion_sound = user_input.get("completion_sound", getattr(chore, 'completion_sound', DEFAULT_COMPLETION_SOUND))
                if vis_entity:
                    chore.visibility_entity = vis_entity
                    chore.visibility_operator = vis_operator
                    chore.visibility_state = vis_state
                else:
                    chore.visibility_entity = ""
                    chore.visibility_operator = "equals"
                    chore.visibility_state = "on"
                mode_in = user_input.get("assignment_mode", getattr(chore, "assignment_mode", "everyone"))
                chore.assignment_mode = mode_in if mode_in in ASSIGNMENT_MODES else "everyone"
                chore.assignment_rotation_anchor = user_input.get("assignment_rotation_anchor", getattr(chore, "assignment_rotation_anchor", "")) or ""
                chore.publish_calendar_entities = list(user_input.get("publish_calendar_entities", getattr(chore, "publish_calendar_entities", []) or []))
                self._edited_chore = chore
                _LOGGER.debug(
                    "Edit chore step 1 - saved visibility fields: entity=%s, operator=%s, state=%s",
                    chore.visibility_entity, chore.visibility_operator, chore.visibility_state
                )
                self._chore_step1_data = {**user_input, "_editing": True, "_chore_id": chore_id}
                schedule_mode = user_input.get("schedule_mode", "specific_days")
                if schedule_mode == "specific_days":
                    return await self.async_step_edit_chore_schedule_specific()
                elif schedule_mode == "one_shot":
                    return await self.async_step_edit_chore_schedule_one_shot()
                else:
                    return await self.async_step_edit_chore_schedule_recurring()

        child_options = [
            selector.SelectOptionDict(value=c.id, label=c.name)
            for c in children
        ]
        # Options are plain strings; labels come from translation_key in strings.json

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
                    options=list(TIME_CATEGORIES),
                    translation_key="time_category",
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional("claim_allowance_minutes", default=getattr(chore, "claim_allowance_minutes", DEFAULT_CLAIM_ALLOWANCE_MINUTES)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=720, step=5, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="min")
            ),
            vol.Required("schedule_mode", default=current_schedule_mode): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["specific_days", "recurring", "one_shot"],
                    translation_key="schedule_mode",
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
        }
        # Add visibility fields — EntitySelector rejects empty string default,
        # so only set default when entity has a value
        vis_entity = getattr(chore, 'visibility_entity', '')
        if vis_entity:
            schema_dict[vol.Optional("visibility_entity", default=vis_entity)] = selector.EntitySelector(
                selector.EntitySelectorConfig()
            )
        else:
            schema_dict[vol.Optional("visibility_entity")] = selector.EntitySelector(
                selector.EntitySelectorConfig()
            )
        schema_dict[vol.Required("visibility_operator", default="none" if not vis_entity else getattr(chore, 'visibility_operator', 'equals'))] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value="none", label="No filter (always show)"),
                    selector.SelectOptionDict(value="equals", label="Equals (exact match)"),
                    selector.SelectOptionDict(value="gte", label="Greater than or equal (>=)"),
                    selector.SelectOptionDict(value="lte", label="Less than or equal (<=)"),
                    selector.SelectOptionDict(value="gt", label="Greater than (>)"),
                    selector.SelectOptionDict(value="lt", label="Less than (<)"),
                    selector.SelectOptionDict(value="not_equals", label="Not equal (!=)"),
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
        schema_dict[vol.Optional("visibility_state", default=getattr(chore, 'visibility_state', '') if vis_entity else "")] = str
        schema_dict[vol.Optional("assignment_mode", default=getattr(chore, "assignment_mode", "everyone"))] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=list(ASSIGNMENT_MODES),
                translation_key="assignment_mode",
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        )
        schema_dict[vol.Optional("assignment_rotation_anchor", default=getattr(chore, "assignment_rotation_anchor", "") or "")] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.DATE)
        )
        existing_calendars = list(getattr(chore, "publish_calendar_entities", []) or [])
        if existing_calendars:
            schema_dict[vol.Optional("publish_calendar_entities", default=existing_calendars)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="calendar", multiple=True)
            )
        else:
            schema_dict[vol.Optional("publish_calendar_entities", default=[])] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="calendar", multiple=True)
            )
        schema_dict[vol.Required("action", default="save")] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=self._get_chore_action_options(chore),
                translation_key="chore_action",
                mode=selector.SelectSelectorMode.LIST,
            )
        )

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
        # Use the chore object from Step 1 if available, otherwise reload it
        chore = self._edited_chore
        if not chore:
            chore_id = self._selected_chore_id
            chore = self.coordinator.get_chore(chore_id)
        if not chore:
            return await self.async_step_manage_chores()

        if user_input is not None:
            # Step 1 data already saved to chore object in async_step_edit_chore
            # Just update schedule-specific fields here
            chore.schedule_mode = "specific_days"
            chore.due_days = user_input.get("due_days", [])
            _LOGGER.debug(
                "Saving specific_days chore %s - due_days=%s, visibility: entity=%s, operator=%s, state=%s",
                chore.name, chore.due_days, chore.visibility_entity, chore.visibility_operator, chore.visibility_state
            )
            # Clear recurring fields
            chore.recurrence = "weekly"
            chore.recurrence_day = ""
            chore.recurrence_start = ""
            chore.first_occurrence_mode = "available_immediately"
            await self.coordinator.async_update_chore(chore)
            self._chore_step1_data = None
            self._edited_chore = None
            return await self.async_step_manage_chores()

        return self.async_show_form(
            step_id="edit_chore_schedule_specific",
            data_schema=vol.Schema({
                vol.Optional("due_days", default=chore.due_days or []): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(DAYS_OF_WEEK),
                        translation_key="due_days_option",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        multiple=True,
                    )
                ),
            }),
            description_placeholders={"chore_name": chore.name},
        )

    async def async_step_edit_chore_schedule_one_shot(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit chore — one-shot schedule (save immediately)."""
        chore = self._edited_chore
        if not chore:
            chore_id = self._selected_chore_id
            chore = self.coordinator.get_chore(chore_id)
        if not chore:
            return await self.async_step_manage_chores()

        chore.schedule_mode = "one_shot"
        chore.daily_limit = 1
        chore.due_days = []
        chore.recurrence = "weekly"
        chore.recurrence_day = ""
        chore.recurrence_start = ""
        chore.first_occurrence_mode = "available_immediately"
        if not chore.created_date:
            from homeassistant.util import dt as dt_util
            chore.created_date = dt_util.as_local(dt_util.now()).date().isoformat()
        await self.coordinator.async_update_chore(chore)
        self._chore_step1_data = None
        self._edited_chore = None
        return await self.async_step_manage_chores()

    async def async_step_edit_chore_schedule_recurring(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Edit chore — Step 2b: recurring schedule."""
        # Use the chore object from Step 1 if available, otherwise reload it
        chore = self._edited_chore
        if not chore:
            chore_id = self._selected_chore_id
            chore = self.coordinator.get_chore(chore_id)
        if not chore:
            return await self.async_step_manage_chores()

        if user_input is not None:
            # Step 1 data already saved to chore object in async_step_edit_chore
            # Just update schedule-recurring fields here
            chore.schedule_mode = "recurring"
            chore.due_days = []
            recurrence = user_input.get("recurrence", "weekly")
            chore.recurrence = recurrence
            raw_day = user_input.get("recurrence_day", "") if recurrence in ("weekly", "every_2_weeks") else ""
            chore.recurrence_day = "" if raw_day == "any_day" else raw_day
            chore.recurrence_start = user_input.get("recurrence_start", "") if recurrence == "every_2_days" else ""
            chore.first_occurrence_mode = user_input.get("first_occurrence_mode", "available_immediately")
            _LOGGER.debug(
                "Saving recurring chore %s - visibility: entity=%s, operator=%s, state=%s",
                chore.name, chore.visibility_entity, chore.visibility_operator, chore.visibility_state
            )
            await self.coordinator.async_update_chore(chore)
            self._chore_step1_data = None
            self._edited_chore = None
            return await self.async_step_manage_chores()

        current_recurrence = getattr(chore, 'recurrence', 'weekly')

        return self.async_show_form(
            step_id="edit_chore_schedule_recurring",
            data_schema=vol.Schema({
                vol.Required("recurrence", default=current_recurrence): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(RECURRENCE_OPTIONS),
                        translation_key="recurrence",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("recurrence_day", default=getattr(chore, 'recurrence_day', '') or "any_day"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["any_day"] + list(DAYS_OF_WEEK),
                        translation_key="recurrence_day_option",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional("recurrence_start", default=getattr(chore, 'recurrence_start', '') or ""): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.DATE)
                ),
                vol.Required("first_occurrence_mode", default=getattr(chore, 'first_occurrence_mode', 'available_immediately')): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["available_immediately", "wait_for_first_occurrence"],
                        translation_key="first_occurrence_mode",
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
        await self._async_load_translations()
        rewards = self.coordinator.storage.get_rewards()
        _m = lambda key, default: self._t(f"options.step.manage_rewards.menu_options.{key}", default)
        menu_options = {"add_reward": _m("add_reward", "Add New Reward")}

        for reward in rewards:
            menu_options[f"edit_reward_{reward.id}"] = f"{reward.name} ({reward.cost} pts)"

        menu_options["init"] = _m("init", "Back to Main Menu")

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
                    pool_enabled=user_input.get("pool_enabled", False),
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
            vol.Optional("pool_enabled", default=False): selector.BooleanSelector(),
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
                reward.pool_enabled = user_input.get(
                    "pool_enabled", getattr(reward, "pool_enabled", False)
                )
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
            vol.Optional("pool_enabled", default=getattr(reward, 'pool_enabled', False)): selector.BooleanSelector(),
            vol.Optional("cost", default=reward.cost): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=10000, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required("action", default="save"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["save", "delete"],
                    translation_key="reward_action",
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
            # Validate milestone format before saving anything
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

            # Batch all settings updates without saving between each one
            self.coordinator.storage.set_points_name(
                user_input.get("points_name", DEFAULT_POINTS_NAME),
            )
            self.coordinator.storage.set_points_icon(
                user_input.get("points_icon", DEFAULT_POINTS_ICON),
            )
            self.coordinator.storage.set_setting(
                "streak_reset_mode",
                user_input.get("streak_reset_mode", "reset"),
            )
            self.coordinator.storage.set_setting(
                "history_days",
                str(int(float(user_input.get("history_days", 90)))),
            )
            self.coordinator.storage.set_setting(
                "weekend_multiplier",
                str(float(user_input.get("weekend_multiplier", 2.0))),
            )
            self.coordinator.storage.set_setting(
                "streak_milestones_enabled",
                "true" if user_input.get("streak_milestones_enabled", True) else "false",
            )
            self.coordinator.storage.set_setting(
                "streak_milestones",
                milestone_input,
            )
            self.coordinator.storage.set_setting(
                "perfect_week_enabled",
                "true" if user_input.get("perfect_week_enabled", True) else "false",
            )
            self.coordinator.storage.set_setting(
                "perfect_week_bonus",
                str(int(float(user_input.get("perfect_week_bonus", 50)))),
            )
            self.coordinator.storage.set_setting(
                "notify_service",
                user_input.get("notify_service", "").strip(),
            )
            self.coordinator.storage.set_setting(
                "calendar_projection_days",
                str(int(float(user_input.get(
                    "calendar_projection_days", DEFAULT_CALENDAR_PROJECTION_DAYS
                )))),
            )
            # Single save and refresh for all settings
            await self.coordinator.storage.async_save()
            await self.coordinator.async_refresh()
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
        try:
            current_calendar_projection_days = int(float(self.coordinator.storage.get_setting(
                "calendar_projection_days", str(DEFAULT_CALENDAR_PROJECTION_DAYS)
            )))
        except (ValueError, TypeError):
            current_calendar_projection_days = DEFAULT_CALENDAR_PROJECTION_DAYS
        current_calendar_projection_days = max(
            MIN_CALENDAR_PROJECTION_DAYS,
            min(MAX_CALENDAR_PROJECTION_DAYS, current_calendar_projection_days),
        )

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
                            options=["reset", "pause"],
                            translation_key="streak_reset_mode",
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
                    vol.Required(
                        "calendar_projection_days",
                        default=current_calendar_projection_days,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_CALENDAR_PROJECTION_DAYS,
                            max=MAX_CALENDAR_PROJECTION_DAYS,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="days",
                        )
                    ),
                }
            ),
        )

    # ==================== DYNAMIC STEP ROUTING ====================

    def __getattr__(self, name: str):
        """Handle dynamic step routing for edit_child_*, edit_chore_*, etc."""
        if name.startswith("async_step_edit_child_"):
            child_id = name.replace("async_step_edit_child_", "")
            if self.coordinator.storage.get_child(child_id):
                self._selected_child_id = child_id
                return self.async_step_edit_child
        elif name.startswith("async_step_edit_chore_"):
            chore_id = name.replace("async_step_edit_chore_", "")
            if self.coordinator.storage.get_chore(chore_id):
                self._selected_chore_id = chore_id
                return self.async_step_edit_chore
        elif name.startswith("async_step_edit_reward_"):
            reward_id = name.replace("async_step_edit_reward_", "")
            if self.coordinator.storage.get_reward(reward_id):
                self._selected_reward_id = reward_id
                return self.async_step_edit_reward
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
