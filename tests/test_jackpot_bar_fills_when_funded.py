"""The classic jackpot bar has to fill up when the pool is fully funded (#874).

The classic rewards card sized each child's segment against an *equal share*
of the goal (cost / number of children) and capped that share at 100%. A
50-point jackpot funded 40 + 10 by two children therefore drew 50% + 20% —
a 70%-full bar under a "50/50" label — and the breakdown read "100%" and
"40%". Segments and percentages both have to be measured against the reward
cost, the same denominator the other render paths already use.
"""

from __future__ import annotations

import pathlib
import re

WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"
REWARDS = (WWW / "taskmate-rewards-card.js").read_text(encoding="utf-8")


def _jackpot_progress_body() -> str:
    """Source of _renderJackpotProgress, up to the next method definition."""
    start = re.search(r"\n  _renderJackpotProgress\(", REWARDS).start()
    tail = REWARDS[start:]
    end = tail.index("\n  _", 1)
    return tail[:end]


def test_the_jackpot_renderer_is_still_where_we_think_it_is():
    # Guards the slice above so the assertions below can't pass vacuously.
    body = _jackpot_progress_body()
    assert "jackpot-segment" in body
    assert "jackpot-breakdown" in body


def test_segment_widths_are_measured_against_the_reward_cost():
    body = _jackpot_progress_body()
    assert re.search(r"contrib\.points\s*/\s*cost", body), (
        "jackpot segment widths must be contribution / cost so the bar fills at 100%"
    )


def test_no_equal_share_weighting_survives_in_the_jackpot_path():
    # The share-per-child model is the #874 root cause: it caps an
    # over-contributing child at their own share, so the bar can never fill
    # unless every child lands exactly on an equal split.
    strays = [
        f"line {n}: {line.strip()}"
        for n, line in enumerate(REWARDS.splitlines(), start=1)
        if re.search(r"weightedProgress|shareOfGoal|expectedContribution|sharePerChild|hasWeightedData", line)
    ]
    assert not strays, "equal-share jackpot weighting is back:\n" + "\n".join(strays)


def test_breakdown_percentage_uses_the_same_share_as_the_segment():
    # The label and the bar disagreed in #874 (100% next to a half-width
    # segment); both now read the single sharePct the renderer computes.
    body = _jackpot_progress_body()
    assert "jackpot-pct" in body
    pct_span = body[body.index("jackpot-pct") :]
    assert re.search(r"sharePct", pct_span), "the breakdown percentage must reuse the segment's sharePct"
