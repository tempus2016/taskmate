"""Diagnostics download for TaskMate.

Settings → Devices & services → TaskMate → ⋮ → Download diagnostics gives a
file a user can attach to a bug report. It carries the configuration that
decides how TaskMate behaves (settings, chores, rewards, the health report)
and how much history there is, but never who the family are: names, linked
users, notify targets, photos, birthdays and secrets are redacted.
"""

from __future__ import annotations

from typing import Any

import homeassistant.const as ha_const
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.loader import async_get_integration

from .const import DOMAIN

# Keys whose values identify a person, reach a device, or unlock something.
TO_REDACT = {
    "name",
    "child_name",
    "user_name",
    "linked_user_id",
    "notify_service",
    "picture_entity",
    "presence_entity",
    "availability_entity",
    "unavailability_entity",
    "birthday",
    "photo_url",
    "image_url",
    "reference_image_url",
    "note",
    "reason",
    "description",
    "ics_token",
    "parent_user_ids",
    "kiosk_pins",
    "service",
    "user_id",
    "tag_ids",
}

# Collections that are history rather than configuration: only their size
# is useful in a bug report.
_HISTORY_KEYS = (
    "completions",
    "reward_claims",
    "points_transactions",
    "awarded_badges",
    "audit_log",
    "allowance_payouts",
    "mandatory_misses",
    "career_score_history",
    "daily_progress",
    "recaps",
    "moods",
    "help_requests",
)


def _size(value: Any) -> int:
    return len(value) if isinstance(value, (list, dict)) else 0


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return redacted diagnostics for a TaskMate config entry."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    integration = await async_get_integration(hass, DOMAIN)
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    platforms: dict[str, int] = {}
    for ent in entities:
        platforms[ent.domain] = platforms.get(ent.domain, 0) + 1

    out: dict[str, Any] = {
        "integration_version": str(integration.version or ""),
        "ha_version": str(getattr(ha_const, "__version__", "")),
        "entry": {"title": "**REDACTED**", "version": entry.version, "options": dict(entry.options)},
        "entities": {"total": len(entities), "by_platform": dict(sorted(platforms.items()))},
    }
    if coordinator is None:
        out["loaded"] = False
        return out

    storage = coordinator.storage
    data = storage.data
    out["loaded"] = True
    out["last_update_success"] = coordinator.last_update_success
    out["health"] = coordinator.health_report()
    out["history_sizes"] = {key: _size(data.get(key)) for key in _HISTORY_KEYS if key in data}
    out["settings"] = async_redact_data(storage.get_settings(), TO_REDACT)
    out["points_name"] = storage.get_points_name()
    # Children: ids are kept so they line up with the chores' assigned_to,
    # everything that says who the child is goes.
    out["children"] = [async_redact_data(c.to_dict(), TO_REDACT) for c in storage.get_children()]
    # Chores and rewards keep their names — "the Bins chore never shows" is
    # what a bug report is about — but not their pictures or descriptions.
    out["chores"] = [
        async_redact_data({**c.to_dict(), "name": c.name}, TO_REDACT - {"name"}) for c in storage.get_chores()
    ]
    out["rewards"] = [
        async_redact_data({**r.to_dict(), "name": r.name}, TO_REDACT - {"name"}) for r in storage.get_rewards()
    ]
    out["notifications"] = async_redact_data(data.get("notification_config") or {}, TO_REDACT)
    return out
