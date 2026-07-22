"""Routine card registration and asset integrity (#676).

The card itself is JavaScript, exercised end-to-end on the dev instance. What
Python can usefully guard is that every card TaskMate claims to ship actually
exists on disk, and that the new one is wired into the resource list — a card
listed but missing 404s on every dashboard load.
"""
from __future__ import annotations

import pathlib
import re

# conftest stubs the whole frontend module, so `CARDS` would be a MagicMock
# and every assertion against it would pass vacuously. Read the real lists out
# of the source instead.
ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
WWW = ROOT / "www"
_FRONTEND_SRC = (ROOT / "frontend.py").read_text(encoding="utf-8")


def _js_list(name: str) -> list[str]:
    block = re.search(rf"{name}: Final = \[(.*?)\]", _FRONTEND_SRC, re.S)
    assert block, f"could not find {name} in frontend.py"
    return re.findall(r'"([^"]+\.js)"', block.group(1))


CARDS = _js_list("CARDS")
RETIRED_CARDS = _js_list("RETIRED_CARDS")


def test_routine_card_is_registered():
    assert "taskmate-routine-card.js" in CARDS


def test_routine_card_file_exists():
    assert (WWW / "taskmate-routine-card.js").is_file()


def test_every_listed_card_exists_on_disk():
    """A listed-but-missing card 404s on every dashboard load."""
    missing = [name for name in CARDS if not (WWW / name).is_file()]
    assert missing == []


def test_no_retired_card_is_also_listed_live():
    assert set(CARDS).isdisjoint(set(RETIRED_CARDS))


def test_retired_cards_are_actually_gone():
    present = [name for name in RETIRED_CARDS if (WWW / name).is_file()]
    assert present == []


def test_routine_card_loads_after_its_shared_helpers():
    """The card calls __taskmate_attrs / __taskmate_localize at render time, so
    the shared modules must be earlier in the load order."""
    order = CARDS
    for helper in ("taskmate-attr-resolver.js", "taskmate-localize.js", "taskmate-design.js"):
        assert order.index(helper) < order.index("taskmate-routine-card.js")


def test_routine_card_registers_its_custom_element():
    source = (WWW / "taskmate-routine-card.js").read_text(encoding="utf-8")
    assert 'customElements.define("taskmate-routine-card"' in source
    assert 'customElements.define("taskmate-routine-card-editor"' in source


def test_routine_card_declares_itself_to_the_card_picker():
    source = (WWW / "taskmate-routine-card.js").read_text(encoding="utf-8")
    assert 'type: "taskmate-routine-card"' in source


def test_routine_card_uses_only_defined_translation_keys():
    """Every routine.* key the card asks for must exist in en.json."""
    import json

    source = (WWW / "taskmate-routine-card.js").read_text(encoding="utf-8")
    used = set(re.findall(r'_t\("(routine\.[a-z_]+)"', source))
    assert used, "expected the card to use routine.* translation keys"

    en = json.loads((WWW / "locales" / "en.json").read_text(encoding="utf-8"))
    missing = sorted(k for k in used if k not in en)
    assert missing == []


def test_routine_keys_present_in_every_locale():
    """A missing key renders as a raw dotted string to the child."""
    import json

    en = json.loads((WWW / "locales" / "en.json").read_text(encoding="utf-8"))
    routine_keys = {k for k in en if k.startswith("routine.")}
    assert routine_keys

    for path in sorted((WWW / "locales").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = sorted(k for k in routine_keys if k not in data)
        assert missing == [], f"{path.name} is missing {missing}"
