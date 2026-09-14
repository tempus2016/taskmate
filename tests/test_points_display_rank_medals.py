"""The "Rank Medals" toggle has to hide every medal, on every render path (#869).

The classic multi-mode grid drew the leader's gold medal from a separate
`isTop` branch that never consulted `show_rank`, so with two children turning
the toggle off removed the silver and left the gold behind.
"""

from __future__ import annotations

import pathlib
import re

WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"
POINTS = (WWW / "taskmate-points-display-card.js").read_text(encoding="utf-8")

GOLD = "\\u{1F947}"
LINES = POINTS.splitlines()

# The gate can sit a few lines above the glyph when the branch opens a
# multi-line template literal (single and cumulative modes both do this).
LOOKBACK = 4


def _medal_lines() -> list[tuple[int, str]]:
    """1-indexed lines that paint a medal, excluding the RANK_MEDAL table itself."""
    return [
        (n, line) for n, line in enumerate(LINES, start=1) if "RANK_MEDAL[" in line and "const RANK_MEDAL" not in line
    ]


def test_there_are_medal_render_sites_to_check():
    # Guards the search above: if the card stopped using RANK_MEDAL this file
    # would otherwise pass vacuously.
    assert len(_medal_lines()) >= 4


def test_every_medal_render_site_is_gated_on_show_rank():
    ungated = [
        f"line {n}: {line.strip()}"
        for n, line in _medal_lines()
        if not re.search(r"show_rank|showRank", "\n".join(LINES[max(0, n - 1 - LOOKBACK) : n]))
    ]
    assert not ungated, "medal rendered without a show_rank gate:\n" + "\n".join(ungated)


def test_medals_only_come_from_the_rank_medal_table():
    # #869 was a second, hardcoded copy of the gold glyph that escaped the
    # gate above by not going through RANK_MEDAL at all.
    strays = [
        f"line {n}: {line.strip()}"
        for n, line in enumerate(LINES, start=1)
        if GOLD in line and "const RANK_MEDAL" not in line
    ]
    assert not strays, "gold medal written out by hand:\n" + "\n".join(strays)
