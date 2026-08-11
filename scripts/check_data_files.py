#!/usr/bin/env python3
"""Parse-check every shipped data file, and cross-check manifest/hacs metadata.

A malformed blueprint or locale file doesn't break the Python tests — it breaks
at install time on a user's Home Assistant, which is the worst place to find out.
This walks every YAML and JSON file we ship and simply proves it parses, then
runs a few cheap consistency checks on the packaging metadata.

Run: python3 scripts/check_data_files.py
Exit code 0 = everything parses, 1 = at least one problem.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
INTEGRATION = REPO_ROOT / "custom_components" / "taskmate"

YAML_DIRS = (REPO_ROOT / "blueprints", REPO_ROOT / "custom_sentences")
JSON_DIRS = (
    INTEGRATION / "translations",
    INTEGRATION / "www" / "locales",
)
JSON_FILES = (INTEGRATION / "manifest.json", REPO_ROOT / "hacs.json")

# Home Assistant loads blueprints with its own loader, which understands !input.
# Plain yaml.safe_load would choke on it, so register a passthrough.
yaml.SafeLoader.add_constructor("!input", lambda loader, node: loader.construct_scalar(node))
yaml.SafeLoader.add_constructor("!secret", lambda loader, node: loader.construct_scalar(node))


def check_yaml(problems: list[str]) -> None:
    for directory in YAML_DIRS:
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.y*ml")):
            rel = path.relative_to(REPO_ROOT)
            try:
                yaml.safe_load(path.read_text(encoding="utf-8"))
                print(f"  OK    {rel}")
            except yaml.YAMLError as err:
                print(f"  FAIL  {rel}")
                problems.append(f"{rel}: invalid YAML — {err}")


def check_json(problems: list[str]) -> None:
    paths = list(JSON_FILES)
    for directory in JSON_DIRS:
        if directory.is_dir():
            paths += sorted(directory.glob("*.json"))

    for path in paths:
        rel = path.relative_to(REPO_ROOT)
        if not path.is_file():
            print(f"  FAIL  {rel} (missing)")
            problems.append(f"{rel}: file not found")
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
            print(f"  OK    {rel}")
        except json.JSONDecodeError as err:
            print(f"  FAIL  {rel}")
            problems.append(f"{rel}: invalid JSON — {err}")


def check_metadata(problems: list[str]) -> None:
    manifest_path = INTEGRATION / "manifest.json"
    hacs_path = REPO_ROOT / "hacs.json"

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hacs = json.loads(hacs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return  # already reported by check_json

    for key in ("domain", "name", "version", "documentation", "issue_tracker", "codeowners"):
        if not manifest.get(key):
            problems.append(f"manifest.json: missing required key '{key}'")

    if manifest.get("domain") != "taskmate":
        problems.append(f"manifest.json: domain is '{manifest.get('domain')}', expected 'taskmate'")

    # HACS is configured for zip_release — release-zip.yml must keep producing
    # this exact filename or the integration becomes uninstallable.
    if hacs.get("zip_release") and hacs.get("filename") != "taskmate.zip":
        problems.append(
            f"hacs.json: zip_release is on but filename is '{hacs.get('filename')}', expected 'taskmate.zip'"
        )

    print(f"  OK    manifest version {manifest.get('version')}, hacs filename {hacs.get('filename')}")


def main() -> int:
    problems: list[str] = []

    print("YAML (blueprints, custom sentences)")
    check_yaml(problems)

    print("\nJSON (manifest, hacs, translations, locales)")
    check_json(problems)

    print("\nPackaging metadata")
    check_metadata(problems)

    print()
    if problems:
        print(f"FAIL — {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1

    print("PASS — all shipped data files parse and metadata is consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
