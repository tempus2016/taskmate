# TaskMate v3.1.0 — Release Notes

_Release date: 2026-04-20_

This release focuses on smarter time-of-day chore handling and a full
rewrite of the card editors to native Home Assistant form components.
It also picks up routine CI dependency bumps.

---

## Highlights

- **Next-period preview + per-chore claim allowance** — chores no longer
  disappear at exact period boundaries. You can see upcoming chores and
  give transition-time chores a configurable grace window.
- **Editors rebuilt with `ha-form`** — all 14 Lovelace card editors now
  use native Home Assistant form components, including an improved
  colour picker, for a pixel-perfect admin UX.

---

## ✨ New features

### Next-period preview + per-chore claim allowance (#113)

Two coordinated UX changes for time-of-day chores:

- **Next-period preview.** Chores in the period immediately after the
  current one (e.g. Afternoon chores shown during Morning) now render on
  the child card as dimmed with a `mdi:lock-clock` badge. They are
  non-claimable until their period starts, at which point they unlock on
  the next render tick — no reload required.
- **Per-chore claim allowance.** Every chore gains an optional
  `claim_allowance_minutes` (default `0`, max `720`). The chore stays
  claimable that many minutes past the end of its assigned time-of-day
  window. Night-period chores are always capped at midnight regardless
  of the allowance value.

Together these remove the "chore disappeared at 12:00 while my kid was
still setting the table" class of problem, while keeping the four fixed
Morning / Afternoon / Evening / Night periods intact.

Added:
- `claim_allowance_minutes` field on the `Chore` model (round-trips
  through HA storage; clamped to `>= 0` on load).
- New config-flow field in the Add Chore, Add Chores (bulk) and Edit
  Chore forms (label "Claim allowance (minutes)", helper text, 0–720
  minute range).
- Helpers in `taskmate-child-card.js`: `_getPeriodHours`,
  `_getCurrentHourMinute`, `_isChorePreviewLocked`,
  `_isChoreInClaimWindow`. `_isTimePeriodElapsed` is now grace-aware.
- New `.chore-locked` CSS class + `mdi:lock-clock` badge for locked
  preview chores.
- Translation keys in `strings.json`, all seven HA `translations/*.json`
  files, and six `www/locales/*.json` card locale files (English and
  en-GB in final copy; French, Portuguese and pt-BR translated;
  Norwegian Bokmål / Nynorsk fall back to English copy).

### Native HA form editors across the card suite

Card editors were migrated to `ha-form` schemas with improved colour
pickers and consistent field layouts.

- **Batch 1 (#108)** — `ha-form` + improved colour picker for 4 card
  editors.
- **Batch 2 (#109)** — `ha-form` + improved colour picker for the
  remaining 10 card editors.

The visual result is pixel-parity with native HA editors, and behaviour
for defaults, validation and helper text is now consistent across
every TaskMate card.

---

## 🧰 Maintenance & CI

Routine dependency bumps for the GitHub Actions used by the release and
validation workflows — keeps the CI matrix current.

- **#84** — `actions/setup-python` bumped from 5 → 6.
- **#85** — `actions/github-script` bumped from 7 → 9.
- **#86** — `actions/checkout` bumped from 4 → 6.

No behavioural changes to released code.

---

## 🔧 Upgrading

Update via HACS, or download the release and copy the contents to
`/config/custom_components/taskmate/`. **Restart Home Assistant** after
updating. Lovelace resources update automatically on restart.

No config migration is required. Existing chores keep their current
behaviour (the new `claim_allowance_minutes` defaults to `0`, which
matches pre-3.1.0 semantics exactly).

---

## Full commit log since v3.0.1

- `6afa632` feat(chores): next-period preview + per-chore claim allowance (#113)
- `a522016` feat(editors): ha-form + improved colour picker for remaining 10 editors (#109)
- `eb2b626` feat(editors): ha-form + improved colour picker for 4 card editors (#108)
- `2de6e31` chore(deps): bump actions/checkout from 4 to 6 (#86)
- `4d071c3` chore(deps): bump actions/github-script from 7 to 9 (#85)
- `7a7e684` chore(deps): bump actions/setup-python from 5 to 6 (#84)
