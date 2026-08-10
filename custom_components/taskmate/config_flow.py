"""Config flow for TaskMate integration.

Only the initial setup flow lives here. Day-to-day configuration (children,
chores, rewards, task groups, settings, notifications, badges, templates, …)
is handled entirely by the dedicated TaskMate admin panel at
``/taskmate-admin``. The legacy options/configure flow was removed in v4.0 —
all of its functionality is available in the panel, and all data is stored in
the integration's own ``Store`` rather than in ``config_entry.options``.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import DEFAULT_POINTS_ICON, DEFAULT_POINTS_NAME, DOMAIN


class TaskMateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for TaskMate."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
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
