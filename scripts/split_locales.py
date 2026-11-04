#!/usr/bin/env python3
"""Split each card/panel locale into the bundles the browser actually loads.

The translation source stays one flat file per language,
``custom_components/taskmate/www/locales/<lang>.json`` — that is what
translators edit, what scripts/check_translations.py compares, and what the
backend reads for notifications and season packs. The browser never loads it.
Instead taskmate-localize.js fetches only the bundle a screen needs:

  locales/<lang>/cards.json   every string the dashboard cards use
  locales/<lang>/editor.json  the visual card editors' strings
  locales/<lang>/panel.json   the admin panel's own strings (the panel also
                              loads cards.json, for the strings it shares)

Which bundle a key belongs to is decided by its name alone, with the rules in
taskmate-localize.js (the block between the BEGIN/END locale-bundles
markers). This script reads the rules from there, so the browser and the split
can never disagree about where a key lives.

Each bundle is complete: a key missing (or blank) in a language is filled at
build time from its fallback chain (pt-BR -> pt -> en-GB, de -> en-GB), exactly
as the browser used to resolve it at run time. So a page loads one file per
bundle and never needs a second, English, copy.

The bundles are generated but committed, so a Home Assistant install that runs
straight from a checkout (the dev instance, a manual copy) works with no build
step, and the HACS zip and release guard need nothing new. CI runs --check, and
the pre-commit hook rewrites them, so they cannot drift from the sources.

Run: python3 scripts/split_locales.py          (rewrite the bundles)
     python3 scripts/split_locales.py --check  (CI: fail if any is stale)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WWW = REPO_ROOT / "custom_components" / "taskmate" / "www"
LOCALES = WWW / "locales"
LOCALIZE_JS = WWW / "taskmate-localize.js"

_BLOCK = re.compile(
    r"// BEGIN locale-bundles[^\n]*\nconst _BUNDLES = (?P<json>\{.*?\});\n// END locale-bundles",
    re.S,
)


def load_config() -> dict:
    """The bundle rules, language list and fallback, read from taskmate-localize.js."""
    match = _BLOCK.search(LOCALIZE_JS.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"{LOCALIZE_JS.relative_to(REPO_ROOT)}: no locale-bundles block")
    return json.loads(match.group("json"))


def bundle_for(key: str, config: dict) -> str:
    """Mirror of _bundleFor() in taskmate-localize.js: the first matching rule wins."""
    for kind, needle, bundle in config["rules"]:
        if (kind == "prefix" and key.startswith(needle)) or (kind == "contains" and needle in key):
            return bundle
    return config["default"]


def chain(lang: str, config: dict) -> list[str]:
    """The language, its base language if it has one, then the fallback."""
    out = [lang]
    if "-" in lang and lang.split("-")[0] in config["langs"]:
        out.append(lang.split("-")[0])
    if config["fallback"] not in out:
        out.append(config["fallback"])
    return out


def build(config: dict) -> dict[Path, str]:
    """Every bundle file's path and exact contents."""
    sources = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(LOCALES.glob("*.json"))}
    fallback = sources[config["fallback"]]
    out: dict[Path, str] = {}
    for lang, strings in sources.items():
        merged: dict[str, str] = {}
        # Source order, with keys only some languages carry appended after.
        for key in list(fallback) + [k for k in strings if k not in fallback]:
            values = [sources[c].get(key) for c in chain(lang, config)]
            present = [v for v in values if v is not None]
            if not present:
                continue
            # A blank string falls through, as the browser used to do.
            merged[key] = next((v for v in present if v), present[-1])
        bundles: dict[str, dict[str, str]] = {name: {} for name in config["bundles"]}
        for key, value in merged.items():
            bundles[bundle_for(key, config)][key] = value
        for name, data in bundles.items():
            text = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
            out[LOCALES / lang / f"{name}.json"] = text
    return out


def problems_with(config: dict) -> list[str]:
    langs = sorted(p.stem for p in LOCALES.glob("*.json"))
    if sorted(config["langs"]) != langs:
        return [
            f"taskmate-localize.js lists languages {sorted(config['langs'])} but locales/ has {langs}; "
            "update the langs list in its locale-bundles block"
        ]
    if config["fallback"] not in langs:
        return [f"fallback language {config['fallback']} has no locales/{config['fallback']}.json"]
    unknown = {rule[2] for rule in config["rules"]} | {config["default"]}
    unknown -= set(config["bundles"])
    if unknown:
        return [f"rules name bundles that are not listed: {sorted(unknown)}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="fail if any bundle is missing or stale")
    args = parser.parse_args()

    config = load_config()
    problems = problems_with(config)
    if problems:
        print("\n".join(problems))
        return 1

    wanted = build(config)
    expected_dirs = {path.parent for path in wanted}
    stray = [path for path in sorted(LOCALES.glob("*/*")) if path not in wanted or path.parent not in expected_dirs]
    stale = [path for path, text in wanted.items() if not path.is_file() or path.read_text(encoding="utf-8") != text]

    if args.check:
        for path in stale:
            print(f"stale: {path.relative_to(REPO_ROOT)}")
        for path in stray:
            print(f"not generated by this script: {path.relative_to(REPO_ROOT)}")
        if stale or stray:
            print("\nThe split locale bundles are out of date. Run: python3 scripts/split_locales.py")
            return 1
        print(f"PASS — {len(wanted)} locale bundles match the sources.")
        return 0

    for path in stale:
        path.parent.mkdir(exist_ok=True)
        path.write_text(wanted[path], encoding="utf-8")
    for path in stray:
        path.unlink()
    print(f"Wrote {len(stale)} of {len(wanted)} locale bundles; removed {len(stray)} stray file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
