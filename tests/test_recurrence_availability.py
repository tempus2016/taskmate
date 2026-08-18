"""recurrence_done_mode was dead code (#803).

The child card reads `chore._isRecurring` and `chore._isAvailableForChild` in
its render path, but nothing ever assigned either field — a repo-wide search
found no assignment anywhere. `undefined && …` is always falsy, so:

* `recurrence_done_mode: dim` never dimmed anything and never made the row
  non-interactive;
* the `.recurrence-label` block was unreachable;
* and `hide` was dead too, because the filter never looked at recurrence at all.

The card cannot compute the window itself: `last_completed` is not exposed to
the frontend and `recurrence` is omitted from the sensor payload when it is the
default weekly. So availability is taken from the authoritative
`chore_availability` matrix, the same one the backend publishes.

Reproduced on the dev instance with a recurring chore anchored in the future:
the matrix reported it unavailable while the card rendered it as tappable under
all three modes.
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate"
CARD = (ROOT / "www" / "taskmate-child-card.js").read_text(encoding="utf-8")


def _filter_source() -> str:
    start = CARD.index("  _filterAndSortChores(chores, child) {")
    return CARD[start : CARD.index("\n  _getTimeCategoryIcon(", start)]


def _row_source() -> str:
    start = CARD.index("  _renderChoreCard(chore, child, pointsIcon")
    return CARD[start : CARD.index("\n  _renderTimedChoreCard(", start)]


class TestFieldsAreActuallyAssigned:
    def test_is_recurring_is_assigned(self):
        assert "_isRecurring =" in _filter_source(), "the card reads chore._isRecurring but never assigns it"

    def test_lock_uses_a_dedicated_field(self):
        """Deliberately NOT chore._isAvailableForChild. That field is also read
        by the picture-mode tile, where a matrix-unavailable chore would become
        an undisablable tile — including losing undo. Reviving it globally is a
        separate question from this fix."""
        src = _filter_source()
        assert "_isRecurrenceLocked =" in src
        assert "_isAvailableForChild =" not in src

    def test_availability_comes_from_the_backend_matrix(self):
        """Not recomputed client-side: last_completed isn't exposed and the
        recurrence maths is calendar-month aware."""
        assert "chore_availability" in _filter_source()

    def test_missing_matrix_defaults_to_available(self):
        """An older backend, or a cold sensor, must not blank the card."""
        assert "!== false" in _filter_source()

    def test_recurring_is_keyed_on_schedule_mode(self):
        assert "'recurring'" in _filter_source() or '"recurring"' in _filter_source()


class TestHideMode:
    def test_filter_honours_hide(self):
        src = _filter_source()
        assert "recurrence_done_mode" in src, "hide was never applied at filter stage"

    def test_hide_does_not_swallow_a_chore_completed_today(self):
        """Ticking a recurring chore makes it unavailable immediately; hiding it
        on the spot would remove the done state and any way to undo."""
        src = _filter_source()
        # The lock is what hide keys on, so the exclusion has to live in it.
        idx = src.index("_isRecurrenceLocked =")
        lock = src[idx : src.index(";", idx)]
        assert "completedToday" in lock, f"the lock must exclude chores completed today, got: {lock!r}"
        assert "_isRecurrenceLocked" in src[src.index("recurrenceDoneMode === 'hide'") - 60 :]


class TestDimMode:
    def test_dim_still_allows_undo(self):
        """recurrenceLocked short-circuits the click handler before the undo
        branch, so it must not fire for a chore completed today."""
        row = _row_source()
        idx = row.index("const recurrenceLocked =")
        stmt = row[idx : row.index(";", idx)]
        assert "isCompletedForToday" in stmt, f"a chore completed today must stay undoable, got: {stmt!r}"

    def test_designed_styles_dim_too(self):
        """The designed row builder computes its own `dimmed` flag."""
        start = CARD.index("    const rows = childChores.map((chore, i) => {")
        rows = CARD[start : CARD.index("_designChoreMeta(r) {", start)]
        assert "_isRecurrenceLocked" in rows, "designed styles never dim an unavailable recurring chore"

    def test_designed_done_button_is_disabled_when_locked(self):
        assert "r.loading || r.blocked || r.recLocked" in CARD


class TestLabelComesAlive:
    def test_label_block_still_present(self):
        assert "recurrence-label" in CARD

    def test_label_falls_back_when_recurrence_is_omitted(self):
        """The sensor omits `recurrence` when it is the default weekly, so the
        label has to cope with it being absent."""
        assert "child.recurring" in CARD


class TestShowModeIsNotTappable:
    """`show` must not leave a dead-tappable chore (#805).

    `async_complete_chore` returns None for a recurring chore still inside its
    window, so a tap does nothing. Leaving the row interactive reproduces the
    "nothing happens" papercut of #794/#799. `dependency_mode` already refuses
    the tap under both dim and show; recurrence conflated styling with
    interactivity and only refused it under dim.
    """

    def test_interactivity_is_separate_from_the_dim_styling(self):
        row = _row_source()
        idx = row.index("const notAvailableRecurrence =")
        stmt = row[idx : row.index(";", idx)]
        # The dim-styling flag stays mode-gated...
        assert "'dim'" in stmt
        # ...but a separate flag must gate the click, without the mode.
        assert "const recurrenceLocked" in row, "show still shares the dim flag, so the row stays clickable"

    def test_click_handler_refuses_under_show_too(self):
        row = _row_source()
        handler = row[row.index("const handleRowClick") : row.index("const isInteractive")]
        assert "recurrenceLocked" in handler

    def test_row_is_marked_non_interactive(self):
        row = _row_source()
        idx = row.index("const isInteractive =")
        assert "recurrenceLocked" in row[idx : row.index(";", idx)]

    def test_designed_styles_already_agreed(self):
        """They gate the button on the lock itself, not on the mode."""
        assert "r.loading || r.blocked || r.recLocked" in CARD

    def test_label_no_longer_promises_normal_behaviour(self):
        import json
        import pathlib

        www = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "taskmate" / "www"
        for path in sorted((www / "locales").glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            value = data["child.editor.recurrence_show"]
            assert "regardless" not in value.lower(), f"{path.name} still promises 'regardless'"
            assert value != "Show — show normally regardless"
