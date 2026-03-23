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


async def async_register_cards(hass: HomeAssistant) -> None:
    """Register and version-update TaskMate Lovelace resources on every startup.

    Safety rules — this function will ONLY ever:
      1. Add missing TaskMate cards (create)
      2. Update the ?v= query string on existing TaskMate cards (update)
    It will NEVER delete any resource. Stale cleanup is removed entirely
    because URL mismatches caused accidental deletion of all resources.
    Only URLs that begin with /taskmate/ are ever touched.
    """
    version = await _async_get_version(hass)
    _LOGGER.info("TaskMate resource manager: version=%s", version)

    lovelace_data = hass.data.get("lovelace")
    if lovelace_data is None:
        _LOGGER.warning("TaskMate: Lovelace not available — skipping resource registration.")
        return

    mode = getattr(lovelace_data, "mode", "storage")
    if mode == "yaml":
        _LOGGER.info("TaskMate: Lovelace YAML mode — add resources manually:")
        for card in CARDS:
            _LOGGER.info("  - url: %s/%s?v=%s  (type: module)", URL_BASE, card, version)
        return

    try:
        resources = lovelace_data.resources
        if resources is None:
            _LOGGER.warning("TaskMate: Lovelace resources object not available.")
            return

        # Force load storage from disk BEFORE reading items.
        # Without this, async_items() returns empty if storage hasn't been
        # read yet — causing us to create duplicate entries which then get
        # wiped when lovelace subsequently loads its own storage file.
        #
        # Browser Mod uses: resources.async_load() + resources.loaded flag
        # WebRTC uses:      resources.async_get_info()
        # We use both as a belt-and-braces approach.
        if hasattr(resources, "loaded") and not resources.loaded:
            await resources.async_load()
            resources.loaded = True
        elif hasattr(resources, "async_get_info"):
            await resources.async_get_info()

        # Build a map of base_url (without ?v=...) -> full resource item
        # ONLY for resources whose URL starts with /taskmate/
        # Everything else is completely ignored
        existing: dict[str, dict] = {}
        all_items = list(resources.async_items())
        _LOGGER.debug("TaskMate: total Lovelace resources = %d", len(all_items))

        for item in all_items:
            url = item.get("url", "")
            base_url = url.split("?")[0]
            if base_url.startswith(URL_BASE + "/"):
                existing[base_url] = item
                _LOGGER.debug("TaskMate: found existing resource: %s", url)

        _LOGGER.info("TaskMate: found %d existing TaskMate resources", len(existing))

        # Add missing cards or update version on existing ones
        # NEVER delete anything
        for card in CARDS:
            card_url = f"{URL_BASE}/{card}"
            versioned_url = f"{card_url}?v={version}"

            if card_url not in existing:
                # Card not registered yet — add it
                await resources.async_create_item(
                    {"url": versioned_url, "res_type": "module"}
                )
                _LOGGER.info("TaskMate: added resource: %s", versioned_url)
            else:
                item = existing[card_url]
                current_url = item.get("url", "")
                if current_url != versioned_url:
                    # Version string changed — update it
                    await resources.async_update_item(
                        item["id"],
                        {"url": versioned_url, "res_type": "module"},
                    )
                    _LOGGER.info(
                        "TaskMate: updated resource: %s -> %s",
                        current_url, versioned_url,
                    )
                else:
                    _LOGGER.debug("TaskMate: resource up to date: %s", versioned_url)

    except Exception as err:  # noqa: BLE001
        _LOGGER.error("TaskMate: error managing Lovelace resources: %s", err)
