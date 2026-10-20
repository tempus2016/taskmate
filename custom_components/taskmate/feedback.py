"""What the admin panel's Help & feedback page fills into a GitHub issue.

The page builds a pre-filled ``issues/new`` link; nothing is sent from Home
Assistant. This gathers the environment half of a bug report — the bit people
get wrong or leave out by hand: versions, how HA and TaskMate are installed,
the Lovelace resource mode, rough sizes and the health check's issue codes.

It never says who the family are: counts only, no names, and the health
check contributes its issue *codes*, not its messages (those name chores).
"""

from __future__ import annotations

import logging
from typing import Any

import homeassistant.const as ha_const
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

REPO_FULL_NAME = "tempus2016/taskmate"

# HA's system_info installation_type → the bug template's dropdown options.
_INSTALL_TYPES = {
    "Home Assistant OS": "haos",
    "Home Assistant Supervised": "supervised",
    "Home Assistant Container": "container",
    "Unsupported Third Party Container": "container",
    "Home Assistant Core": "core",
}


async def _installation_type(hass: HomeAssistant) -> tuple[str, str]:
    """(template key, HA's own wording, e.g. "Home Assistant OS")."""
    try:
        from homeassistant.helpers.system_info import async_get_system_info

        info = await async_get_system_info(hass)
    except Exception:  # noqa: BLE001 — a report without it is still a report
        _LOGGER.debug("TaskMate feedback: system info unavailable", exc_info=True)
        return "unknown", ""
    raw = str(info.get("installation_type") or "")
    return _INSTALL_TYPES.get(raw, "unknown"), raw


def _install_method(hass: HomeAssistant) -> str:
    """How TaskMate itself was installed: hacs_default, hacs_custom, manual or unknown.

    Reads HACS's in-memory repository list. That is HACS's internal API, so
    any surprise in its shape degrades to "unknown" rather than failing.
    """
    if "hacs" not in hass.config.components:
        return "manual"
    try:
        hacs = hass.data.get("hacs")
        repo = hacs.repositories.get_by_full_name(REPO_FULL_NAME)
        if repo is None:
            return "manual"
        if not getattr(repo.data, "installed", True):
            return "manual"
        return "hacs_default" if hacs.repositories.is_default(str(repo.data.id)) else "hacs_custom"
    except Exception:  # noqa: BLE001
        _LOGGER.debug("TaskMate feedback: could not read HACS repositories", exc_info=True)
        return "unknown"


def _lovelace_mode(hass: HomeAssistant) -> str:
    """storage, yaml or unknown — where Lovelace resources are managed.

    HA keeps this as a dataclass since 2024.12 (``mode``, later renamed
    ``resource_mode``) and as a plain dict before it.
    """
    data = hass.data.get("lovelace")
    if data is None:
        return "unknown"
    if isinstance(data, dict):
        mode = data.get("resource_mode") or data.get("mode")
    else:
        mode = getattr(data, "resource_mode", None) or getattr(data, "mode", None)
    mode = str(mode or "").lower()
    return mode if mode in ("storage", "yaml") else "unknown"


def _entry_id(hass: HomeAssistant, coordinator) -> str:
    entry = getattr(coordinator, "config_entry", None)
    if entry is not None and getattr(entry, "entry_id", None):
        return str(entry.entry_id)
    for key, value in hass.data.get(DOMAIN, {}).items():
        if value is coordinator:
            return str(key)
    return ""


async def async_feedback_info(hass: HomeAssistant, coordinator) -> dict[str, Any]:
    """The environment summary for a bug report or feature request."""
    integration = await async_get_integration(hass, DOMAIN)
    install_type, install_type_raw = await _installation_type(hass)
    storage = coordinator.storage
    children = storage.get_children()
    try:
        health = coordinator.health_report()
        health_codes = sorted({str(i.get("code", "")) for i in health.get("issues", []) if i.get("code")})
    except Exception:  # noqa: BLE001
        _LOGGER.debug("TaskMate feedback: health report failed", exc_info=True)
        health_codes = []
    settings = storage.get_settings() or {}
    return {
        "integration_version": str(integration.version or ""),
        "ha_version": str(getattr(ha_const, "__version__", "")),
        "installation_type": install_type,
        "installation_type_raw": install_type_raw,
        "install_method": _install_method(hass),
        "lovelace_mode": _lovelace_mode(hass),
        "language": str(getattr(hass.config, "language", "") or ""),
        "counts": {
            "children": sum(1 for c in children if not getattr(c, "is_adult", False)),
            "adults": sum(1 for c in children if getattr(c, "is_adult", False)),
            "chores": len(storage.get_chores()),
            "rewards": len(storage.get_rewards()),
        },
        "card_design": str(settings.get("card_design") or "classic"),
        "health_codes": health_codes,
        "entry_id": _entry_id(hass, coordinator),
    }
