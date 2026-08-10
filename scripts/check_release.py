#!/usr/bin/env python3
"""Verify manifest.json's version matches the release tag exactly.

HACS reads the version out of manifest.json, not out of the git tag. If the two
disagree, HACS shows one version and installs another — and for pre-releases the
full tag string matters, so tag v5.2.0-beta.1 must be version "5.2.0-beta.1",
not "5.2.0".

Run: python3 scripts/check_release.py v5.2.0
Exit code 0 = match, 1 = mismatch.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "custom_components" / "taskmate" / "manifest.json"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_release.py <tag>")
        return 2

    tag = argv[1]
    expected = tag[1:] if tag.startswith("v") else tag
    version = json.loads(MANIFEST.read_text(encoding="utf-8")).get("version")

    print(f"tag:              {tag}")
    print(f"expected version: {expected}")
    print(f"manifest version: {version}")

    if version != expected:
        print()
        print(f"FAIL — manifest.json says '{version}' but the tag implies '{expected}'.")
        print("Fix manifest.json (full tag string, including any -beta.N suffix), then re-tag.")
        return 1

    print("\nPASS — manifest version matches the release tag.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
