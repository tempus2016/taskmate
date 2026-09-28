"""Wishlist and bounty row actions must stay reachable on a narrow panel.

The Active wishes table (Wishlists tab) and the Bounties table carried their
action buttons in a trailing column. With the HA sidebar open at 1400 px, or
at tablet/phone widths, the table outgrows the panel and that last column
lands past the right edge of the scroll container — Fulfil clipped, delete
out of sight (issue #951). They now ride inside the pinned name cell, the way
the Chores table already does it (#533/#568).

Structural (grep over source) because the layout depends on the surrounding
Home Assistant frontend, which no unit test instantiates; the rendering was
checked with browserless screenshots at 1400/1024/768/400 px.
"""

from __future__ import annotations

import pathlib
import re

PANEL = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www" / "taskmate-panel.js"


def _method(name: str) -> str:
    src = PANEL.read_text(encoding="utf-8")
    start = src.index(f"\n  {name}(")
    end = src.index("\n  }\n", start)
    return src[start:end]


def _first_cell(row_html: str) -> str:
    """The first <td>…</td> of a row template (cells nest <div>s, not <td>s)."""
    start = row_html.index("<td")
    return row_html[start : row_html.index("</td>", start)]


def _active_wishes_table() -> str:
    body = _method("_renderWishlistsTab")
    start = body.index("const activeHtml")
    return body[start : body.index("const pledgesHtml", start)]


def test_active_wish_actions_ride_in_the_pinned_name_cell():
    table = _active_wishes_table()
    row = table[table.index('<tr class="tm-row">') :]
    cell = _first_cell(row)
    assert "tm-col-sticky" in cell
    assert "${main}" in cell, "Pledge/Fulfil button must sit in the pinned name cell"
    assert 'data-act="wish-delete"' in cell, "delete must sit in the pinned name cell"


def test_active_wishes_table_has_no_trailing_actions_column():
    head = _active_wishes_table()
    head = head[head.index("<thead>") : head.index("</thead>")]
    assert "<th></th>" not in head
    assert 'class="tm-col-sticky"' in head


def test_bounty_actions_ride_in_the_pinned_name_cell():
    row = _method("_renderBountyRow")
    row = row[row.index('<tr class="tm-row">') :]
    cell = _first_cell(row)
    assert "tm-col-sticky" in cell
    assert "${actions}" in cell, "bounty actions must sit in the pinned name cell"


def test_bounties_table_has_no_trailing_actions_column():
    body = _method("_renderBountiesTab")
    head = body[body.index("<thead>") : body.index("</thead>")]
    assert "<th></th>" not in head
    assert 'class="tm-col-sticky"' in head
    assert 'colspan="5"' in body, "the empty-state row must span the 5 remaining columns"


def test_wrapping_name_cell_lets_text_and_actions_wrap():
    src = PANEL.read_text(encoding="utf-8")
    rule = re.search(r"\.tm-table td\.tm-cell-wrap\s*\{([^}]*)\}", src)
    assert rule and "white-space: normal" in rule.group(1)
    rule = re.search(r"\.tm-name-cell-wrap\s*\{([^}]*)\}", src)
    assert rule and "flex-wrap: wrap" in rule.group(1)
