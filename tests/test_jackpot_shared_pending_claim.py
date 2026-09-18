"""A pending jackpot claim must lock the reward for every contributor (#873).

A jackpot is funded from one shared pool and redeemed once per funding cycle.
The coordinator side of this is covered functionally in
tests/test_coordinator_rewards.py; this module guards the card side, which is
structural because the rewards card computes `hasPendingClaim` twice — once in
the classic `_renderRewardRow` path and once in the design-system path. A fix
applied to only one of them leaves the bug alive under four of the five card
designs, which has happened repeatedly.
"""

from __future__ import annotations

import pathlib
import re

CARD = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "taskmate"
    / "www"
    / "taskmate-rewards-card.js"
)

# Matches a hasPendingClaim assignment plus the predicate body that follows it.
_PENDING_BLOCK = re.compile(
    r"const hasPendingClaim\s*=\s*pendingClaims\.some\(\s*c\s*=>(?P<body>.*?)\);",
    re.DOTALL,
)


def _pending_claim_predicates() -> list[str]:
    return [m.group("body") for m in _PENDING_BLOCK.finditer(CARD.read_text(encoding="utf-8"))]


def test_both_render_paths_compute_a_pending_claim():
    # Classic row + design-system row. If this count changes, the new path
    # needs the jackpot term too.
    assert len(_pending_claim_predicates()) == 2


def test_every_render_path_treats_a_jackpot_claim_as_shared():
    for body in _pending_claim_predicates():
        assert "isJackpot" in body, (
            "a hasPendingClaim predicate filters only on the selected child — "
            "a jackpot claim from one contributor must lock the reward for all "
            "of them (#873)"
        )
