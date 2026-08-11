"""The panel's undo gate must match the backend's, not use its own allow-list (#761).

The Admin Panel used to render its undo button only for reasons starting with
"Penalty: " or "Bonus: ". That allow-list silently hid undo for manual
add/remove adjustments, which `PointsMixin.async_undo_transaction` explicitly
supports and which `taskmate-activity-card` already offers.

There are now three copies of the deny-list — Python, the card, the panel — so
these tests pin them against each other. The backend's own comment warns that a
new derived reason must be added to its list; a third copy is a third place to
forget.
"""

from __future__ import annotations

import pathlib
import re

from custom_components.taskmate.coord_points import PointsMixin

WWW = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"
PANEL = (WWW / "taskmate-panel.js").read_text(encoding="utf-8")
ACTIVITY_CARD = (WWW / "taskmate-activity-card.js").read_text(encoding="utf-8")


def _js_deny_prefixes(src: str, label: str) -> list[str]:
    """Pull the string literals out of a JS _UNDO_DENY_PREFIXES getter."""
    block = re.search(r"_UNDO_DENY_PREFIXES\(\)\s*\{\s*return\s*\[(.*?)\]", src, re.S)
    assert block, f"{label} has no _UNDO_DENY_PREFIXES getter"
    prefixes = re.findall(r'"([^"]+)"', block.group(1))
    assert prefixes, f"{label} _UNDO_DENY_PREFIXES is empty"
    return prefixes


def test_panel_no_longer_uses_a_reason_allow_list():
    # The bug: an allow-list of just these two prefixes. Its absence is the fix.
    assert 'startsWith("Penalty: ") || t.reason.startsWith("Bonus: ")' not in PANEL, (
        "the panel is still gating undo on a Penalty:/Bonus: allow-list, which hides undo for manual adjustments"
    )


def test_panel_gates_undo_on_reversibility():
    block = re.search(r"_renderActivityTab\(\) \{(.*?)\n  \}", PANEL, re.S)
    assert block, "could not find _renderActivityTab"
    body = block.group(1)
    assert "_txnReversible(" in body, "the transactions table must decide undoability via _txnReversible"


def test_panel_has_a_reversibility_helper():
    block = re.search(r"_txnReversible\(reason\) \{(.*?)\n  \}", PANEL, re.S)
    assert block, "could not find _txnReversible in the panel"
    body = block.group(1)
    assert "_UNDO_DENY_PREFIXES" in body, "must consult the deny-list"
    assert "startsWith" in body, "deny-list entries are prefixes, not exact matches"


def test_all_three_deny_lists_are_identical():
    backend = list(PointsMixin._UNDO_DENY_PREFIXES)
    panel = _js_deny_prefixes(PANEL, "taskmate-panel.js")
    card = _js_deny_prefixes(ACTIVITY_CARD, "taskmate-activity-card.js")
    assert panel == backend, f"panel deny-list drifted from coord_points.py: panel={panel} backend={backend}"
    assert card == backend, f"activity-card deny-list drifted from coord_points.py: card={card} backend={backend}"


def test_manual_adjustments_are_reversible_under_the_deny_list():
    # The whole point of #761: these reasons must NOT be denied.
    deny = tuple(PointsMixin._UNDO_DENY_PREFIXES)
    for reason in (
        "Admin panel adjustment",  # the #746 quick buttons
        "Broke a window",  # a free-text reason from the custom dialog
        "",  # a bare add_points/remove_points call
        "Penalty: Messy room",
        "Bonus: Helped out",
    ):
        assert not reason.startswith(deny), f"{reason!r} should be reversible"


def test_derived_transactions_are_still_denied():
    deny = tuple(PointsMixin._UNDO_DENY_PREFIXES)
    for reason in (
        "Weekend bonus (×2)",
        "Streak milestone bonus (7 day streak!)",
        "Perfect week bonus!",
        "Allocated to pool: Cinema trip",
        "Pool refund (reward deleted): Cinema trip",
        "Points decay",
        "Savings interest",
        "Badge: 50 Chores Completed",
    ):
        assert reason.startswith(deny), f"{reason!r} must stay non-undoable"
