#!/usr/bin/env python3
"""Check that every locale carries exactly the same keys as English.

TaskMate ships two independent string catalogues:

  custom_components/taskmate/translations/  — nested, used by Home Assistant
                                              (config flow, services, entities)
  custom_components/taskmate/www/locales/   — flat dotted keys, used by the
                                              Lovelace cards and admin panel

Both must stay in lockstep with ``en.json``. A missing key renders as a raw
key (or English) in the UI; a stray key is dead weight that hides a typo.
This script is the CI gate behind "new strings ship translated in the same PR".

Run: python3 scripts/check_translations.py
Exit code 0 = all locales match English, 1 = drift found.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_LOCALE = "en"

CATALOGUES = (
    ("Home Assistant translations", REPO_ROOT / "custom_components" / "taskmate" / "translations"),
    ("Card/panel locales", REPO_ROOT / "custom_components" / "taskmate" / "www" / "locales"),
)


def flatten(obj, prefix=""):
    """Flatten a nested dict into dotted key paths, so both catalogue shapes compare alike."""
    keys = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                keys |= flatten(value, path)
            else:
                keys.add(path)
    return keys


def load_keys(path: Path) -> set[str]:
    with path.open(encoding="utf-8") as handle:
        return flatten(json.load(handle))


def check_catalogue(label: str, directory: Path) -> list[str]:
    problems: list[str] = []
    base_file = directory / f"{BASE_LOCALE}.json"

    if not base_file.is_file():
        return [f"{label}: missing base locale {base_file.relative_to(REPO_ROOT)}"]

    base_keys = load_keys(base_file)
    locales = sorted(p for p in directory.glob("*.json") if p.stem != BASE_LOCALE)

    print(f"\n{label} ({directory.relative_to(REPO_ROOT)})")
    print(f"  {BASE_LOCALE}.json: {len(base_keys)} keys (reference)")

    for locale_file in locales:
        try:
            locale_keys = load_keys(locale_file)
        except json.JSONDecodeError as err:
            problems.append(f"{label}: {locale_file.name} is not valid JSON — {err}")
            print(f"  {locale_file.name}: INVALID JSON")
            continue

        missing = sorted(base_keys - locale_keys)
        extra = sorted(locale_keys - base_keys)

        if not missing and not extra:
            print(f"  {locale_file.name}: OK ({len(locale_keys)} keys)")
            continue

        print(f"  {locale_file.name}: {len(missing)} missing, {len(extra)} extra")
        for key in missing:
            print(f"      missing: {key}")
            problems.append(f"{label}: {locale_file.name} is missing key '{key}'")
        for key in extra:
            print(f"      extra:   {key}")
            problems.append(f"{label}: {locale_file.name} has key '{key}' not present in {BASE_LOCALE}.json")

    return problems


def main() -> int:
    problems: list[str] = []
    for label, directory in CATALOGUES:
        if not directory.is_dir():
            problems.append(f"{label}: directory {directory} not found")
            continue
        problems += check_catalogue(label, directory)

    print()
    if problems:
        print(f"FAIL — {len(problems)} translation key problem(s).")
        print("Every user-facing string must ship translated into all locales in the same PR.")
        return 1

    print("PASS — all locales match English key-for-key.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
