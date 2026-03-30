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
    """Register and update TaskMate Lovelace resources.

    On first install: adds all card resources.
    On every restart: updates the version query string on existing TaskMate
    resources so browsers fetch fresh JS after an upgrade. Only touches URLs
    that start with the TaskMate URL base — never modifies other integrations.
    """
    version = await _async_get_version(hass)

    lovelace_data = hass.data.get("lovelace")
    if lovelace_data is None:
        _LOGGER.warning("Lovelace not available — add resources manually.")
        return

    mode = getattr(lovelace_data, "mode", "storage")
    if mode == "yaml":
        _LOGGER.info("Lovelace YAML mode — add these resources to configuration.yaml:")
        for card in CARDS:
            _LOGGER.info("  - url: %s/%s?v=%s  (type: module)", URL_BASE, card, version)
        return

    try:
        resources = lovelace_data.resources
        if resources is None:
            _LOGGER.warning("Lovelace resources not available.")
            return

        # Build a map of base_url -> resource item for existing TaskMate entries only
        # Never touch entries from other integrations
        existing: dict[str, dict] = {}
        for item in resources.async_items():
            url = item.get("url", "")
            base_url = url.split("?")[0]
            if base_url.startswith(URL_BASE + "/"):
                existing[base_url] = item

        expected_cards = {f"{URL_BASE}/{card}" for card in CARDS}

        for card in CARDS:
            card_url = f"{URL_BASE}/{card}"
            versioned_url = f"{card_url}?v={version}"

            if card_url not in existing:
                # New card — add it
                await resources.async_create_item(
                    {"url": versioned_url, "res_type": "module"}
                )
                _LOGGER.info("Registered new Lovelace resource: %s", versioned_url)
            else:
                # Existing card — update version if it has changed
                item = existing[card_url]
                if item.get("url") != versioned_url:
                    await resources.async_update_item(
                        item["id"],
                        {"url": versioned_url, "res_type": "module"},
                    )
                    _LOGGER.info(
                        "Updated Lovelace resource: %s -> %s",
                        item.get("url"), versioned_url,
                    )
                else:
                    _LOGGER.debug("Resource already at correct version: %s", versioned_url)

        # Remove TaskMate resources that are no longer in the CARDS list
        # (handles card renames or removals between versions)
        for base_url, item in existing.items():
            if base_url not in expected_cards:
                await resources.async_delete_item(item["id"])
                _LOGGER.info("Removed stale TaskMate resource: %s", base_url)

    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not manage Lovelace resources: %s", err)
