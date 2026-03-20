"""Frontend registration for TaskMate custom cards."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Final

from homeassistant.components.http import StaticPathConfig
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# URL base path for serving static files
URL_BASE: Final = "/taskmate"

# List of card files to register as Lovelace resources
CARDS: Final = [
    "taskmate-child-card.js",
    "taskmate-rewards-card.js",
    "taskmate-approvals-card.js",
    "taskmate-points-card.js",
    "taskmate-reorder-card.js",
    "taskmate-overview-card.js",
    "taskmate-activity-card.js",
    "taskmate-streak-card.js",
    "taskmate-weekly-card.js",
    "taskmate-graph-card.js",
    "taskmate-reward-progress-card.js",
    "taskmate-leaderboard-card.js",
    "taskmate-parent-dashboard-card.js",
]

# JS modules to load globally (for config flow sound preview)
GLOBAL_MODULES: Final = [
    "taskmate-config-sounds.js",
]

# Track if frontend is registered
FRONTEND_REGISTERED: Final = "frontend_registered"


async def _async_get_version(hass: HomeAssistant) -> str:
    """Get version from manifest.json for cache busting (async-safe)."""
    manifest_path = Path(__file__).parent / "manifest.json"
    try:
        content = await hass.async_add_executor_job(
            manifest_path.read_text, "utf-8"
        )
        return json.loads(content).get("version", "1.0.0")
    except Exception:  # noqa: BLE001
        return "1.0.0"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register static paths for serving card JavaScript files."""
    # Only register once
    if hass.data.get(DOMAIN, {}).get(FRONTEND_REGISTERED):
        _LOGGER.debug("Frontend already registered, skipping")
        return

    www_path = Path(__file__).parent / "www"

    if not www_path.exists():
        _LOGGER.warning("www directory not found at %s", www_path)
        return

    # Register the www folder as a static path
    await hass.http.async_register_static_paths(
        [StaticPathConfig(URL_BASE, str(www_path), False)]
    )

    _LOGGER.debug("Registered static path: %s -> %s", URL_BASE, www_path)

    # Register global JS modules (loaded on all pages, including config flow)
    version = await _async_get_version(hass)
    for module in GLOBAL_MODULES:
        module_url = f"{URL_BASE}/{module}?v={version}"
        add_extra_js_url(hass, module_url)
        _LOGGER.info("Registered global frontend module: %s", module_url)

    # Mark as registered
    hass.data.setdefault(DOMAIN, {})[FRONTEND_REGISTERED] = True


async def async_register_cards(hass: HomeAssistant, first_install: bool = False) -> None:
    """Register Lovelace resources — only on first install, never on restart.

    On subsequent startups this is a no-op. Resources are managed manually
    after the initial install to prevent corrupting other integrations' entries.
    """
    version = await _async_get_version(hass)

    if not first_install:
        # On restart, just log the URLs in case manual action is needed
        _LOGGER.debug("TaskMate card resources should already be registered.")
        return

    lovelace_data = hass.data.get("lovelace")
    if lovelace_data is None:
        _LOGGER.warning("Lovelace not available — add resources manually.")
        return

    mode = getattr(lovelace_data, "mode", "storage")
    if mode == "yaml":
        _LOGGER.info("Lovelace YAML mode — add these resources to configuration.yaml:")
        for card in CARDS:
            _LOGGER.info("  - url: %s/%s  (type: module)", URL_BASE, card)
        return

    try:
        resources = lovelace_data.resources
        if resources is None:
            _LOGGER.warning("Lovelace resources not available.")
            return

        # Build existing TaskMate URLs
        existing = set()
        for item in resources.async_items():
            url = item.get("url", "").split("?")[0]
            if url.startswith(URL_BASE + "/"):
                existing.add(url)

        # Add only missing cards
        for card in CARDS:
            card_url = f"{URL_BASE}/{card}"
            if card_url not in existing:
                await resources.async_create_item(
                    {"url": f"{card_url}?v={version}", "res_type": "module"}
                )
                _LOGGER.info("Registered Lovelace resource: %s", card_url)

    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not register resources: %s", err)
