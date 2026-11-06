"""The suggested points name in Home Assistant's language (no HA imports, so it is testable)."""

from __future__ import annotations

import json
from pathlib import Path

from .const import DEFAULT_POINTS_NAME


def default_points_name(language: str | None) -> str:
    """The suggested points name ("Stars") in HA's language, as the panel wizard says it."""
    locales = Path(__file__).parent / "www" / "locales"
    for lang in (language, (language or "").split("-")[0], "en"):
        if not lang:
            continue
        try:
            data = json.loads((locales / f"{lang}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        name = data.get("wizard.pname_stars")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return DEFAULT_POINTS_NAME
