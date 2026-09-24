"""The sticker chart card: a sticker per point, filling towards one reward.

This is the card the children actually look at, so the guards here are about
the things that would quietly break it for them: losing the companion-sensor
lookup (blank chores), losing the shared face helper (no account photo), a
translation key that never landed, or an unbounded sticker row.

Structural, like the other card guards — the behaviour lives in JavaScript
that the Python suite cannot execute.
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
WWW = ROOT / "custom_components" / "taskmate" / "www"
LOCALES = WWW / "locales"
CARD = (WWW / "taskmate-sticker-chart-card.js").read_text(encoding="utf-8")
FRONTEND = (ROOT / "custom_components" / "taskmate" / "frontend.py").read_text(encoding="utf-8")


def test_card_is_registered_for_serving():
    """An unregistered card file is never served, so the card simply is not there."""
    assert '"taskmate-sticker-chart-card.js"' in FRONTEND


def test_card_is_offered_in_the_lovelace_picker():
    assert 'type: "taskmate-sticker-chart-card"' in CARD
    assert "window.customCards" in CARD
    assert "customElements.define(\"taskmate-sticker-chart-card\"" in CARD
    assert "customElements.define(\"taskmate-sticker-chart-card-editor\"" in CARD


def test_reads_through_the_companion_sensor_resolver():
    """chores/rewards live on companion sensors; reading the overview entity's
    own attributes would leave the goal and today's count empty."""
    assert "__taskmate_attrs" in CARD


def test_uses_the_shared_face_helper():
    """So a child with a linked account picture shows their photo here too."""
    assert "__taskmate_child_visual" in CARD
    assert "tm-face-img" in CARD


def test_sticker_row_is_bounded():
    """A 500-point reward must not paint 500 emoji into the page."""
    assert "MAX_STICKERS" in CARD
    cap = int(re.search(r"const MAX_STICKERS = (\d+)", CARD).group(1))
    assert 0 < cap <= 200
    assert "Math.min(earned, MAX_STICKERS)" in CARD


def test_stickers_never_run_past_the_goal():
    assert "Math.min(points, goal)" in CARD


def test_sticker_row_is_announced_as_one_image():
    """A screen reader reading out 40 individual emoji is useless."""
    assert 'role="img"' in CARD
    assert "sticker_chart.stickers_alt" in CARD


def _keys_used() -> set[str]:
    return set(re.findall(r"""_t\(\s*["']([a-z_0-9.]+)["']""", CARD))


def test_every_translation_key_it_uses_exists():
    used = _keys_used()
    assert used, "no translation keys found — did _t() get renamed?"
    for name in sorted(p.name for p in LOCALES.glob("*.json")):
        with open(LOCALES / name, encoding="utf-8") as fh:
            catalogue = json.load(fh)
        missing = sorted(k for k in used if k not in catalogue)
        assert missing == [], f"{name} is missing: {missing}"


def test_no_hardcoded_english_in_the_rendered_copy():
    """Every child-facing string goes through _t so the chart speaks the
    household's language."""
    for phrase in ("Sticker Chart", "jobs done", "GOAL REACHED", "to the reward"):
        rendered = re.findall(rf"html`[^`]*{re.escape(phrase)}", CARD)
        assert rendered == [], f"hardcoded {phrase!r} in a template: {rendered}"


# ── The tiles ────────────────────────────────────────────────────────────────


def test_tiles_complete_through_the_same_path_as_the_child_card():
    """Pressing the button entity keeps HA automations on it firing; the
    service is the fallback before the entity is registered."""
    assert '__taskmate_find_button(this.hass, child.id, "complete", row.chore.id)' in CARD
    assert '"button", "press"' in CARD
    assert '"taskmate", "complete_chore"' in CARD


def test_card_filters_specific_days_itself():
    """The backend's availability matrix deliberately leaves day-of-week to the
    cards; skipping it would show Monday-only chores every day."""
    assert 'chore.schedule_mode === "specific_days"' in CARD
    assert "days.includes(todayDow)" in CARD


def test_a_finished_sticker_never_vanishes():
    """A recurring chore can flip unavailable once done; it must stay on the
    chart as a finished sticker rather than disappearing."""
    assert "perChild[childId] === false && mine.length === 0" in CARD


def test_optimistic_ticks_are_reconciled_not_just_ignored():
    """A leftover optimistic tick resurrected a 'done' tile after an undo
    (found in the browser harness). willUpdate must drop it once HA catches up."""
    assert "willUpdate(changedProps)" in CARD
    assert "landed < opt.base + opt.count" in CARD


def test_undo_goes_through_the_parent_gated_service():
    assert '"taskmate", "reject_chore"' in CARD
    assert "completion_id: latest.completion_id" in CARD


def test_photo_evidence_chores_are_not_faked_from_a_tile():
    """A tile cannot capture a photo, so it must not submit one without."""
    assert "row.chore.require_photo" in CARD
    assert "sticker_chart.needs_photo" in CARD


def test_claiming_a_reward_takes_two_taps():
    """Spending a child's stars must not happen on one stray tap."""
    assert "CONFIRM_MS" in CARD
    assert "this._confirming !== child.id" in CARD
    assert '"taskmate", "claim_reward"' in CARD


def test_weekly_goal_counts_this_weeks_jobs():
    """`goal: week` fills the blocks with stars earned since Monday out of all
    the week's jobs can give (from the overview sensor), so stars earned past a
    reward's cost can't pile up unseen."""
    assert 'this.config.goal === "week"' in CARD
    assert "child.week_points_available" in CARD
    assert "child.week_points_earned" in CARD
    assert "sticker_chart.week_goal" in CARD
    assert "sticker_chart.week_perfect" in CARD


def test_weekly_goal_is_offered_in_the_editor_and_reward_stays_default():
    assert 'name: "goal"' in CARD
    assert 'if (key === "goal" && value === "reward") continue;' in CARD


def test_big_goals_keep_the_block_look():
    """A goal past MAX_BLOCKS used to switch to a plain bar, so one child's
    chart looked unlike the other's. Each block now stands for several stars."""
    assert 'class="bar"' not in CARD
    assert "Math.ceil(goal / MAX_BLOCKS)" in CARD
    assert "sticker_chart.block_key" in CARD


def test_a_past_day_is_ticked_through_the_backdating_service():
    """The admin panel shows this card for a past day (`config.date`): ticks
    must log that day as a parent, never as today."""
    assert "completed_date: pastDate" in CARD
    assert "as_parent: true" in CARD
    assert "this.dayCompletions" in CARD
    assert '"taskmate-day-changed"' in CARD
    # rotation chores can't be logged for a past day, so aren't offered
    assert 'if (past && mode !== "everyone") continue;' in CARD


def test_the_card_finds_lit_outside_a_dashboard():
    """In the admin panel there is no hui-masonry-view; the card must still load."""
    assert '"home-assistant-main"' in CARD
    assert 'hasOwnProperty.call(C.prototype, "html")' in CARD


def test_a_refused_tap_explains_itself():
    """A tablet signed in as the wrong user gets "Unauthorized" from HA; the
    chart must say what that means instead of showing the raw error."""
    assert "_failed(err, child)" in CARD
    assert "sticker_chart.not_allowed" in CARD
    assert "/unauthori|not authorized|admin|permission|forbidden/i" in CARD
