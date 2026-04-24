"""Sidebar panel registration for the TaskMate admin UI."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Final

from homeassistant.components import panel_custom
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PANEL_REGISTERED: Final = "panel_registered"
PANEL_URL_PATH: Final = "taskmate"
PANEL_WEBCOMPONENT: Final = "taskmate-panel"
PANEL_MODULE_FILE: Final = "taskmate-panel.js"


async def _async_get_version(hass: HomeAssistant) -> str:
    """Read manifest.json version off the executor for cache busting."""
    manifest_path = Path(__file__).parent / "manifest.json"
    try:
        content = await hass.async_add_executor_job(manifest_path.read_text, "utf-8")
        return json.loads(content).get("version", "1.0.0")
    except (OSError, json.JSONDecodeError, AttributeError):
        return "1.0.0"


async def async_register_panel(hass: HomeAssistant) -> None:
    """Register the TaskMate sidebar panel.

    Idempotent — running this on a second config-entry setup is a no-op.
    The panel JS is served by frontend.async_register_frontend() out of the
    integration's own www/ directory at /taskmate/.
    """
    if hass.data.get(DOMAIN, {}).get(PANEL_REGISTERED):
        _LOGGER.debug("TaskMate panel already registered, skipping")
        return

    version = await _async_get_version(hass)
    module_url = f"/taskmate/{PANEL_MODULE_FILE}?v={version}"

    try:
        await panel_custom.async_register_panel(
            hass,
            webcomponent_name=PANEL_WEBCOMPONENT,
            frontend_url_path=PANEL_URL_PATH,
            sidebar_title="TaskMate",
            sidebar_icon="mdi:checkbox-marked-circle-plus-outline",
            module_url=module_url,
            embed_iframe=False,
            require_admin=True,
        )
    except ValueError as err:
        # async_register_panel raises ValueError if the url_path is taken —
        # treat as already-registered and move on.
        _LOGGER.warning("TaskMate panel registration skipped: %s", err)
        hass.data.setdefault(DOMAIN, {})[PANEL_REGISTERED] = True
        return

    hass.data.setdefault(DOMAIN, {})[PANEL_REGISTERED] = True
    _LOGGER.info("Registered TaskMate sidebar panel at /%s (module: %s)", PANEL_URL_PATH, module_url)
