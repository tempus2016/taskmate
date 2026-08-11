"""Every shipped Lovelace card must wire into the per-card design system.

The photo-gallery and family-goal cards shipped ignoring `card_design`
entirely (issue #725) — the same gap the routine card had (#721). Nothing
failed; the cards just rendered identically under every style. This guard
makes a card that skips the design layer a test failure rather than a
silently-inconsistent card discovered months later.

The check is structural (grep over source) because the behaviour is invisible
to a functional test — a card that ignores the design tokens renders perfectly,
just always in the classic look.
"""

from __future__ import annotations

import pathlib

WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"

# Cards that legitimately do not reference __taskmate_design directly:
#   the two incentive wrappers delegate their whole render to
#   createIncentiveCard(), which lives in taskmate-incentive-card.js and does
#   wire the design system.
_WRAPPER_EXEMPT = {"taskmate-bonuses-card.js", "taskmate-penalties-card.js"}


def _card_files() -> list[pathlib.Path]:
    return sorted(WWW.glob("taskmate-*-card.js"))


def test_there_are_card_files_to_check():
    assert _card_files(), "expected to find *-card.js files"


def test_every_card_wires_the_design_system():
    missing = []
    for f in _card_files():
        src = f.read_text(encoding="utf-8")
        if f.name in _WRAPPER_EXEMPT:
            # Must actually be a thin wrapper, or the exemption is a lie.
            assert "createIncentiveCard" in src, f"{f.name} is exempt but not a wrapper"
            continue
        if "__taskmate_design" not in src:
            missing.append(f.name)
    assert missing == [], (
        f"these cards never reference the design system, so they ignore "
        f"card_design and render identically under every style: {missing}"
    )


def test_cards_that_name_the_design_layer_actually_use_it():
    """A card that mentions __taskmate_design but never resolves or applies a
    design, nor pulls in the token styles, is not really wired in."""
    offenders = []
    for f in _card_files():
        if f.name in _WRAPPER_EXEMPT:
            continue
        src = f.read_text(encoding="utf-8")
        if "__taskmate_design" not in src:
            continue
        uses_it = ".styles()" in src or "editorOptions" in src or ".apply(" in src or ".resolve(" in src
        if not uses_it:
            offenders.append(f.name)
    assert offenders == [], f"cards that name the design layer but never use it: {offenders}"
