"""Cards must not subscribe to the custom badge event, and must read `badge_id`.

Two defects, one guard (issue #752):

1. The badges card and the child card subscribed to `taskmate_badge_earned`
   over the WebSocket. Home Assistant only lets non-admin users subscribe to an
   allowlisted set of core events, so every child's dashboard logged
   "Refusing to allow <user> to subscribe to event taskmate_badge_earned" on
   every load. Newly-earned badges are now detected by diffing the badges
   sensor's `earned` attribute, which rides on `state_changed` and is allowed
   for everyone.

2. `ChildBadgesSensor` publishes earned entries keyed `badge_id`, but the
   templates compared against `b.id` — undefined on those entries — so the
   "just earned" highlight could never match. Both cards now read the id
   through `window.__taskmate_badge_id`.

Structural (grep over source) because neither defect is visible to a
functional test: the cards render perfectly either way.
"""

from __future__ import annotations

import pathlib
import re

WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"

BADGE_CARDS = ("taskmate-badges-card.js", "taskmate-child-card.js")


def _src(name: str) -> str:
    return (WWW / name).read_text(encoding="utf-8")


def test_no_card_subscribes_to_the_badge_event():
    """A custom-event subscription is refused for non-admins and logs an error."""
    offenders = []
    for f in sorted(WWW.glob("*.js")):
        src = f.read_text(encoding="utf-8")
        # Comments explaining why we no longer subscribe are fine; a real call
        # is not.
        if re.search(r"subscribeEvents\s*\(", src):
            offenders.append(f.name)
    assert offenders == [], (
        "these files call subscribeEvents(); Home Assistant refuses custom-event "
        f"subscriptions from non-admin users and logs an error each time: {offenders}"
    )


def test_badge_id_helper_exists():
    src = _src("taskmate-attr-resolver.js")
    assert "window.__taskmate_badge_id" in src, "the shared badge-id helper is gone; the cards depend on it"


def test_badge_cards_read_the_id_through_the_helper():
    for name in BADGE_CARDS:
        src = _src(name)
        assert "__taskmate_badge_id" in src, f"{name} does not use the badge-id helper"


def test_badge_cards_do_not_compare_against_the_undefined_id_field():
    """`String(b.id)` on a sensor badge entry is the literal string "undefined"."""
    offenders = []
    for name in BADGE_CARDS:
        for line in _src(name).splitlines():
            if "just-earned" not in line:
                continue
            if re.search(r"String\(\s*b\.id\s*\)", line):
                offenders.append(f"{name}: {line.strip()[:100]}")
    assert offenders == [], (
        "badge entries from ChildBadgesSensor are keyed badge_id, not id — "
        f"these comparisons can never match: {offenders}"
    )


def test_both_child_card_render_paths_highlight_the_new_badge():
    """Classic and designed paths each need the highlight (the recurring bug)."""
    hits = [
        line
        for line in _src("taskmate-child-card.js").splitlines()
        if "just-earned" in line and "__taskmate_badge_id" in line
    ]
    assert len(hits) >= 2, (
        "expected the just-earned highlight on BOTH the classic and designed "
        f"render paths of the child card, found {len(hits)}"
    )
