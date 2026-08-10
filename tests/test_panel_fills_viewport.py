"""The admin panel must not size itself with a percentage-height chain.

The panel is nested as ``taskmate-panel → ha-panel-custom →
partial-panel-resolver → ha-drawer``, and the middle two are ``display: inline``
with ``height: auto``. ``height: 100%`` on the panel therefore only resolves
while some ancestor happens to carry a definite height. Where it doesn't, the
shell collapses to its content height and, because the shell is a two-column
grid, the row becomes as tall as the taller column — so the nav column visibly
stops partway down every section with little content (issue #754).

Structural (grep over source) because the collapse depends on the surrounding
Home Assistant frontend, which no unit test instantiates.
"""

from __future__ import annotations

import pathlib
import re

PANEL = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www" / "taskmate-panel.js"


def test_panel_stylesheet_is_not_cut_short_by_a_stray_backtick():
    """The whole panel stylesheet is one JS template literal.

    A backtick inside it — easily typed when quoting a CSS property in a
    comment — closes the literal early. The file can still parse, so
    `node --check` passes and only the running panel breaks: `_styles()`
    returns a truncated `<style>` with no closing tag, the panel renders
    with no CSS, and every section looks blank-ish. Catch it statically.
    """
    src = PANEL.read_text(encoding="utf-8")
    start = src.index("return `<style>")
    body_start = src.index("`", start) + 1
    end = src.index("`", body_start)
    css = src[body_start:end]
    assert "</style>" in css, (
        "the panel stylesheet template literal ends before its </style> — "
        "something inside it (usually a backtick in a comment) closed it early"
    )


def _block(selector: str) -> str:
    """Return the CSS declarations of the first rule for `selector`.

    Comments are stripped so a note *explaining* the old `height: 100%` does
    not read as the declaration itself.
    """
    src = PANEL.read_text(encoding="utf-8")
    match = re.search(
        r"(?:^|\n)\s*" + re.escape(selector) + r"\s*\{(.*?)\}",
        src,
        re.DOTALL,
    )
    assert match, f"no CSS rule found for {selector}"
    return re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.DOTALL)


def test_panel_host_is_exactly_one_viewport_tall():
    rules = _block("taskmate-panel")
    assert re.search(r"(?<!min-)height:\s*100dvh", rules), (
        "the panel host needs a viewport-based height; without it the panel "
        "collapses to content height wherever the ancestor chain is auto"
    )
    assert re.search(r"height:\s*100%", rules) is None, (
        "the panel host must not fall back on height:100% — that is the percentage chain this fix removes"
    )
    assert "min-height: 100dvh" not in rules, (
        "a floor-only rule lets a long section grow the panel past the "
        "viewport, scrolling the nav column off the page instead of scrolling "
        "the body — the shell manages its own internal scroll"
    )


def test_panel_host_is_a_flex_column():
    rules = _block("taskmate-panel")
    assert "display: flex" in rules and "flex-direction: column" in rules, (
        "the shell fills the panel via flex; the host has to be the flex column"
    )


def test_shell_flexes_instead_of_claiming_a_percentage_height():
    rules = _block(".tm-shell")
    assert re.search(r"height:\s*100%", rules) is None, (
        ".tm-shell must not use height:100%; it resolves to auto whenever the ancestor chain has no definite height"
    )
    assert "flex: 1 1 auto" in rules, ".tm-shell must flex to fill the panel"
    assert "min-height: 0" in rules, (
        "a flex item defaults to min-height:auto, which would force the grid back to its content height"
    )
