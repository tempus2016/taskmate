"""Every chore-icon site renders an uploaded image through one resolver (#750).

The classic/designed split is this codebase's recurring failure — a feature that
works on classic and is invisible on the other four styles, three times over,
and #755 was itself a fix for exactly that. Sites 1-2 and 4-5 below are each a
classic/designed pair.
"""
from __future__ import annotations

import pathlib
import re

WWW = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components" / "taskmate" / "www"
)
DESIGN = (WWW / "taskmate-design.js").read_text(encoding="utf-8")
CHILD = (WWW / "taskmate-child-card.js").read_text(encoding="utf-8")
REORDER = (WWW / "taskmate-reorder-card.js").read_text(encoding="utf-8")
ROUTINE = (WWW / "taskmate-routine-card.js").read_text(encoding="utf-8")
ACTIVITY = (WWW / "taskmate-activity-card.js").read_text(encoding="utf-8")

# Six sites, not seven. taskmate-activity-card.js was originally listed as a
# seventh, but its only `c.icon` read is the FILTER CHIP row (the
# all/chores/rewards/adjustments selector); its event rows render a
# category glyph, `.activity-icon t-<klass>`, chosen by transaction type and
# never the chore's own icon. So it has no chore-icon site to convert.

RESOLVER = "__taskmate_chore_visual"


def test_the_resolver_exists_and_is_global():
    assert f"window.{RESOLVER}" in DESIGN


def test_the_resolver_implements_image_over_icon_over_none():
    # design.js guards its globals with `x = x || function ...`, so the regex
    # has to tolerate that idiom between the `=` and the `function`.
    block = re.search(
        rf"{RESOLVER}\s*=\s*(?:window\.\w+\s*\|\|\s*)?function[^{{]*\{{(.*?)\n  \}};",
        DESIGN, re.S,
    )
    assert block, "could not find the resolver body"
    body = block.group(1)
    assert body.index("image_url") < body.index(".icon"), "image must win over icon"
    assert '"none"' in body or "'none'" in body


def _fn(src: str, name: str) -> str:
    """Extract a method body, anchored to its DEFINITION at class indent.

    A naive src.index(f"{name}(") finds the first *call site* for several of
    these — `_renderPreReaderTile` is called ~1000 lines above where it is
    defined — which would silently scan the wrong block.
    """
    m = re.search(rf"\n  {re.escape(name)}\(", src)
    assert m, f"no definition of {name}"
    start = m.start() + 1
    nxt = re.search(r"\n  [_a-zA-Z]+\(", src[start + 10:])
    return src[start: start + 10 + nxt.start()] if nxt else src[start:]


def test_child_card_classic_badge_uses_the_resolver():
    assert RESOLVER in _fn(CHILD, "_choreNumberBadge")


def test_child_card_designed_glyph_uses_the_resolver():
    assert RESOLVER in _fn(CHILD, "_choreGlyph")


def test_child_card_pre_reader_tile_uses_the_resolver():
    assert RESOLVER in _fn(CHILD, "_renderPreReaderTile")


def test_reorder_card_designed_item_uses_the_resolver():
    assert RESOLVER in _fn(REORDER, "_renderDesignedChoreItem")


def test_reorder_card_has_two_resolving_paths():
    # The classic path is a separate render function from the designed one.
    assert REORDER.count(RESOLVER) >= 2, (
        "both reorder paths must resolve, or the image works on one style only"
    )


def test_routine_card_uses_the_resolver():
    assert RESOLVER in ROUTINE


def test_activity_card_is_not_a_chore_icon_site():
    # Guards the scope decision: if someone later renders a chore icon here,
    # this fails and forces them to route it through the resolver too.
    assert "filter_chores" in ACTIVITY, "the c.icon read here is the filter chips"
    assert "activity-icon t-" in ACTIVITY, "event rows use a type glyph, not chore.icon"
    assert "chore.icon" not in ACTIVITY


def test_every_card_that_showed_a_chore_icon_now_resolves():
    for name, src in (("child", CHILD), ("reorder", REORDER), ("routine", ROUTINE)):
        assert RESOLVER in src, f"{name} card never calls the resolver"


def test_chore_images_are_decorative_for_screen_readers():
    # Every slot already sits with the chore name, so alt text would
    # double-announce. Scoped to the <img> tags this feature adds — the child
    # card's avatar <img> legitimately carries a meaningful alt.
    for name, src in (("child", CHILD), ("reorder", REORDER), ("routine", ROUTINE)):
        tags = [t for t in re.findall(r"<img[^>]*>", src) if "v.url" in t]
        assert tags, f"{name} card renders no chore image <img>"
        for tag in tags:
            assert 'alt=""' in tag, f'{name} card chore <img> needs alt="": {tag}'
            assert 'loading="lazy"' in tag, f"{name} card chore <img> should lazy-load"


def test_image_slots_neutralise_the_min_size_trap():
    # Grid/flex items default to min-*:auto, whose content-based minimum is the
    # image's intrinsic aspect ratio. Without min-*:0 a PORTRAIT photo overflows
    # a square slot (measured 64x90 in a 64x64 pre-reader tile) because that
    # minimum beats height:100%. Landscape photos hide the bug entirely.
    for name, src in (("child", CHILD), ("reorder", REORDER), ("routine", ROUTINE)):
        rules = re.findall(r"\.[\w-]*(?:img|-img)[^{]*\{[^}]*\}", src)
        rules = [r for r in rules if "object-fit" in r]
        assert rules, f"{name} card has no chore-image CSS rule"
        for rule in rules:
            assert "min-width: 0" in rule and "min-height: 0" in rule, (
                f"{name} card image rule missing min-*:0 — a portrait photo "
                f"will overflow its slot: {' '.join(rule.split())[:120]}"
            )
