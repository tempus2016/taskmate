"""Template operations mixin for TaskMateCoordinator."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .models import Chore, generate_id, optional_float
from .templates import BUILT_IN_IDS, BUILT_IN_TEMPLATES, TEMPLATE_CHORE_FIELDS

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class TemplatesMixin:
    """Mixin providing template CRUD and application logic."""

    def get_all_templates(self) -> list[dict]:
        """Return built-in + custom templates."""
        custom = self.storage.get_custom_templates()
        return list(BUILT_IN_TEMPLATES) + custom

    def get_template(self, template_id: str) -> dict | None:
        """Return a single template by ID (built-in or custom)."""
        for tpl in BUILT_IN_TEMPLATES:
            if tpl["id"] == template_id:
                return dict(tpl)
        return self.storage.get_custom_template(template_id)

    async def async_apply_template(self, chores: list[dict]) -> list[str]:
        """Create chores from a template's chore definitions. Returns created IDs."""
        if not chores:
            raise ValueError("Cannot apply template with no chores")
        created_ids = []
        for chore_def in chores:
            chore = Chore(
                name=chore_def.get("name", "Unnamed"),
                points=chore_def.get("points", 10),
                description=chore_def.get("description", ""),
                assigned_to=list(chore_def.get("assigned_to", [])),
                requires_approval=chore_def.get("requires_approval", False),
                time_category=chore_def.get("time_category", "anytime"),
                daily_limit=chore_def.get("daily_limit", 1),
                completion_sound=chore_def.get("completion_sound", "coin"),
                schedule_mode=chore_def.get("schedule_mode", "specific_days"),
                due_days=list(chore_def.get("due_days", [])),
                recurrence=chore_def.get("recurrence", "weekly"),
                recurrence_day=chore_def.get("recurrence_day", ""),
                recurrence_start=chore_def.get("recurrence_start", ""),
                first_occurrence_mode=chore_def.get("first_occurrence_mode", "available_immediately"),
                assignment_mode=chore_def.get("assignment_mode", "everyone"),
                require_availability=chore_def.get("require_availability", False),
                visibility_entity=chore_def.get("visibility_entity", ""),
                visibility_state=chore_def.get("visibility_state", "on"),
                visibility_operator=chore_def.get("visibility_operator", "equals"),
                weather_entity=chore_def.get("weather_entity", ""),
                weather_block_conditions=list(chore_def.get("weather_block_conditions", [])),
                weather_temp_min=optional_float(chore_def.get("weather_temp_min")),
                weather_temp_max=optional_float(chore_def.get("weather_temp_max")),
                weather_wind_max=optional_float(chore_def.get("weather_wind_max")),
                task_type=chore_def.get("task_type", "standard"),
                timed_rate_points=chore_def.get("timed_rate_points", 10),
                timed_rate_minutes=chore_def.get("timed_rate_minutes", 5),
                timed_max_daily_minutes=chore_def.get("timed_max_daily_minutes", 0),
            )
            self.storage.add_chore(chore)
            created_ids.append(chore.id)
        await self.storage.async_save()
        await self.async_refresh()
        return created_ids

    async def async_save_template_from_chores(
        self, chore_ids: list[str], name: str, icon: str
    ) -> str:
        """Save existing chores as a custom template pack."""
        if not chore_ids:
            raise ValueError("At least one chore must be selected")
        chores_data = []
        for cid in chore_ids:
            chore = self.storage.get_chore(cid)
            if chore is None:
                continue
            chore_dict = {k: v for k, v in chore.to_dict().items() if k in TEMPLATE_CHORE_FIELDS}
            chores_data.append(chore_dict)
        if not chores_data:
            raise ValueError("No valid chores found for selected IDs")
        tpl_id = generate_id()
        template = {
            "id": tpl_id,
            "name": name.strip(),
            "icon": icon or "mdi:clipboard-list",
            "builtin": False,
            "chores": chores_data,
        }
        self.storage.add_custom_template(template)
        await self.storage.async_save()
        return tpl_id

    async def async_create_template(
        self, name: str, icon: str, chores: list[dict]
    ) -> str:
        """Create a new custom template from scratch."""
        if not chores:
            raise ValueError("Template must have at least one chore")
        tpl_id = generate_id()
        template = {
            "id": tpl_id,
            "name": name.strip(),
            "icon": icon or "mdi:clipboard-list",
            "builtin": False,
            "chores": chores,
        }
        self.storage.add_custom_template(template)
        await self.storage.async_save()
        return tpl_id

    async def async_update_template(
        self, template_id: str, *, name: str | None = None, icon: str | None = None, chores: list[dict] | None = None
    ) -> None:
        """Update a custom template. Raises for built-in templates."""
        if template_id in BUILT_IN_IDS:
            raise ValueError(f"Cannot modify built-in template '{template_id}'")
        updates = {}
        if name is not None:
            updates["name"] = name.strip()
        if icon is not None:
            updates["icon"] = icon
        if chores is not None:
            updates["chores"] = chores
        self.storage.update_custom_template(template_id, updates)
        await self.storage.async_save()

    async def async_delete_template(self, template_id: str) -> None:
        """Delete a custom template. Raises for built-in templates."""
        if template_id in BUILT_IN_IDS:
            raise ValueError(f"Cannot delete built-in template '{template_id}'")
        self.storage.remove_custom_template(template_id)
        await self.storage.async_save()
