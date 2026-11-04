"""The split locale bundles (scripts/split_locales.py).

The browser loads locales/<lang>/{cards,editor,panel}.json rather than the
whole catalogue. These tests keep the committed bundles in step with the
sources and keep keys in the bundle of the screen that uses them: a card
literal routed to the panel bundle would make every dashboard fetch the
panel's ~200 KB of strings again.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WWW = ROOT / "custom_components" / "taskmate" / "www"

_spec = importlib.util.spec_from_file_location("split_locales", ROOT / "scripts" / "split_locales.py")
split_locales = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(split_locales)

CONFIG = split_locales.load_config()
EN_GB = json.loads((WWW / "locales" / "en-GB.json").read_text(encoding="utf-8"))
_LITERAL = re.compile(r"""['"`]([A-Za-z_][\w-]*(?:\.[\w-]+)+)['"`]""")


def _keys_in(paths) -> set[str]:
    found: set[str] = set()
    for path in paths:
        found |= {k for k in _LITERAL.findall(path.read_text(encoding="utf-8")) if k in EN_GB}
    return found


def test_committed_bundles_match_the_sources():
    wanted = split_locales.build(CONFIG)
    for path, text in wanted.items():
        assert path.is_file(), f"{path} missing: run python3 scripts/split_locales.py"
        assert path.read_text(encoding="utf-8") == text, f"{path} stale: run python3 scripts/split_locales.py"
    assert split_locales.problems_with(CONFIG) == []


def test_each_language_splits_into_every_key_exactly_once():
    for lang_dir in sorted(p for p in (WWW / "locales").iterdir() if p.is_dir()):
        seen: dict[str, str] = {}
        for bundle in CONFIG["bundles"]:
            data = json.loads((lang_dir / f"{bundle}.json").read_text(encoding="utf-8"))
            for key in data:
                assert key not in seen, f"{lang_dir.name}: {key} in {seen[key]} and {bundle}"
                assert split_locales.bundle_for(key, CONFIG) == bundle
                seen[key] = bundle
        assert set(seen) == set(EN_GB), lang_dir.name


def test_a_missing_key_takes_the_fallback_chain_at_build_time(monkeypatch, tmp_path):
    (tmp_path / "en-GB.json").write_text(json.dumps({"common.a": "A", "common.b": "B", "panel.c": "C"}))
    (tmp_path / "pt.json").write_text(json.dumps({"common.a": "pt-A", "common.b": "pt-B", "panel.c": ""}))
    (tmp_path / "pt-BR.json").write_text(json.dumps({"common.a": "br-A", "panel.c": ""}))
    monkeypatch.setattr(split_locales, "LOCALES", tmp_path)
    config = {**CONFIG, "langs": ["en-GB", "pt", "pt-BR"]}
    out = {p.relative_to(tmp_path).as_posix(): json.loads(t) for p, t in split_locales.build(config).items()}
    assert out["pt-BR/cards.json"] == {"common.a": "br-A", "common.b": "pt-B"}
    # A blank string falls through to the next language that has words.
    assert out["pt-BR/panel.json"] == {"panel.c": "C"}


def test_card_strings_stay_out_of_the_panel_and_editor_bundles():
    cards = sorted(p for p in WWW.glob("taskmate-*.js") if p.name != "taskmate-panel.js")
    wrong = {k: split_locales.bundle_for(k, CONFIG) for k in _keys_in(cards)}
    wrong = {k: b for k, b in wrong.items() if b != "cards"}
    assert not wrong, f"card code uses keys from other bundles: {wrong}"


def test_editor_strings_come_from_the_editor_or_cards_bundle():
    keys = _keys_in(sorted((WWW / "editors").glob("*.js")))
    assert keys
    stray = {k for k in keys if split_locales.bundle_for(k, CONFIG) not in ("editor", "cards")}
    assert not stray, stray


def test_panel_strings_come_from_the_panel_or_cards_bundle():
    keys = _keys_in([WWW / "taskmate-panel.js"])
    stray = {k for k in keys if split_locales.bundle_for(k, CONFIG) not in ("panel", "cards")}
    assert not stray, stray


def test_the_dashboard_bundle_is_a_fraction_of_the_catalogue():
    full = (WWW / "locales" / "de.json").stat().st_size
    cards = (WWW / "locales" / "de" / "cards.json").stat().st_size
    assert cards < full * 0.4, (cards, full)
