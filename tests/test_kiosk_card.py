"""Kiosk card registration and source guards (#930).

The behaviour is exercised in tests/frontend/taskmate-kiosk-card.test.cjs.
These guard what a JS test can't see: that the card ships and loads after its
helpers, that every string it asks for is translated, and that the source
never grows a parent action or a way to keep a PIN on the client.
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
WWW = ROOT / "www"
SOURCE = (WWW / "taskmate-kiosk-card.js").read_text(encoding="utf-8")
PANEL = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")


def _cards() -> list[str]:
    src = (ROOT / "frontend.py").read_text(encoding="utf-8")
    block = re.search(r"CARDS: Final = \[(.*?)\]", src, re.S)
    assert block
    return re.findall(r'"([^"]+\.js)"', block.group(1))


def test_kiosk_card_is_registered_after_its_helpers():
    cards = _cards()
    assert "taskmate-kiosk-card.js" in cards
    for helper in ("taskmate-attr-resolver.js", "taskmate-localize.js", "taskmate-design.js"):
        assert cards.index(helper) < cards.index("taskmate-kiosk-card.js")


def test_kiosk_card_defines_card_and_editor():
    assert 'customElements.define("taskmate-kiosk-card"' in SOURCE
    assert 'customElements.define("taskmate-kiosk-card-editor"' in SOURCE
    assert 'type: "taskmate-kiosk-card"' in SOURCE
    assert "getConfigElement" in SOURCE


def test_kiosk_card_wires_the_design_system():
    assert "__taskmate_design.apply(" in SOURCE
    assert ".styles()" in SOURCE
    assert "editorOptions" in SOURCE
    assert "colourPicker" in SOURCE  # header_color
    assert SOURCE.count("var(--tmd-") >= 30


def _used_keys(source: str, prefix: str) -> set[str]:
    return set(re.findall(rf'_t\("({prefix}[a-z_.]+)"', source))


def test_every_string_the_card_uses_is_translated_everywhere():
    used = _used_keys(SOURCE, "") | _used_keys(PANEL, "panel.child_kiosk") | _used_keys(PANEL, "panel.toast_kiosk")
    assert any(k.startswith("kiosk.") for k in used)
    assert {"panel.child_kiosk_pin_label", "panel.toast_kiosk_pin_invalid"} <= used
    for path in sorted((WWW / "locales").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = sorted(k for k in used if k not in data)
        assert missing == [], f"{path.name} is missing {missing}"


def test_no_parent_action_in_the_kiosk():
    """Approve/reject, complete-as-parent, points and reward claims have no
    place on a shared child-facing tablet, and there's no toggle for them."""
    services = set(re.findall(r'callService\("(\w+)",\s*"(\w+)"', SOURCE))
    assert services == {("button", "press"), ("taskmate", "complete_chore"), ("taskmate", "undo_chore")}
    for forbidden in (
        "as_parent",
        "approve_",
        "reject_",
        "claim_reward",
        "apply_penalty",
        "adjust_points",
        "show_parent_actions",
    ):
        assert forbidden not in SOURCE


def test_pin_is_checked_on_the_server_and_never_kept():
    assert '"taskmate/kiosk/verify_pin"' in SOURCE
    assert "localStorage" not in SOURCE
    assert "sessionStorage" not in SOURCE
    # The card only learns whether a PIN exists.
    assert "pin_hash" not in SOURCE and "pbkdf2" not in SOURCE
