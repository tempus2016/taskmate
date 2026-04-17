# TaskMate — Full System Audit

Scope: complete review of the TaskMate Home Assistant custom integration at
this repository (Python backend, Lit-based frontend cards, translations,
assets, CI workflows, docs).

## Files Reviewed

### Python backend — `custom_components/taskmate/`
- `__init__.py` (service registration, setup/unload)
- `binary_sensor.py`, `button.py`, `sensor.py`
- `config_flow.py` (options flow, edit wizards)
- `const.py` (constants, service names)
- `coordinator.py` (core business logic, ~52 KB)
- `frontend.py` (card registration)
- `models.py` (data classes, id generation)
- `storage.py` (persistence)
- `manifest.json`, `services.yaml`, `strings.json`

### Frontend cards — `custom_components/taskmate/www/`
- `taskmate-activity-card.js`
- `taskmate-approvals-card.js`
- `taskmate-bonuses-card.js`
- `taskmate-child-card.js` (~75 KB — largest)
- `taskmate-config-sounds.js`
- `taskmate-graph-card.js`
- `taskmate-leaderboard-card.js`
- `taskmate-localize.js`
- `taskmate-overview-card.js`
- `taskmate-parent-dashboard-card.js`
- `taskmate-penalties-card.js`
- `taskmate-points-card.js`
- `taskmate-points-display-card.js`
- `taskmate-reorder-card.js`
- `taskmate-reward-progress-card.js`
- `taskmate-rewards-card.js`
- `taskmate-streak-card.js`
- `taskmate-weekly-card.js`
- `locales/` (runtime locale JSON)
- 10 × `fart*.mp3` (~400 KB total)

### Translations
- `custom_components/taskmate/translations/` — en, en-GB, fr, nb, nn, pt, pt-BR (active)
- `translation_files/` — en, fr only (stale duplicate)

### Tests — `tests/`
- `conftest.py`, `test_coordinator_logic.py`, `test_coordinator_rewards.py`,
  `test_models.py`, `test_storage.py`

### Infrastructure / docs
- `README.md`, `hacs.json`, `pytest.ini`, `.gitignore`, `LICENSE`
- `.github/workflows/` — `hassfest.yaml`, `release-announcement.yml`, `tests.yml`
- `.github/ISSUE_TEMPLATE/` — `bug_report.yml`, `feature_request.yml`, `config.yml`
- `.github/.DS_Store` (junk, committed)
- `images/` — 17 PNGs, 2.0 MB total
- `logo.svg`, `images/logo.svg`

---

## 1. Functionality

### Python
- **`SERVICE_RESET_DAILY`** is defined in `const.py:200` but never registered in
  `__init__.py:_async_register_services`. Any automation calling it will fail
  with "service not found".
- **Missing `await`** on `hass.bus.async_fire(...)` in
  `__init__.py:223` (`handle_preview_sound`). The call is a coroutine; without
  the await, the event may fire after the handler returns or be dropped.
- **Dynamic `__getattr__` routing** in `TaskMateOptionsFlow`
  (`config_flow.py:1272-1289`) stores `self._selected_child_id` before
  returning a bound `async_step_edit_child`. If two edit steps interleave, the
  id is overwritten and the wrong entity is edited.
- **Unsafe coordinator access**: `self.coordinator` property
  (`config_flow.py:95`) assumes `hass.data[DOMAIN][entry_id]` exists. Early
  flow steps or rapid entry re-creation can raise `KeyError`.

### Frontend
- **XSS in graph tooltip**: `taskmate-graph-card.js:527` sets
  `tooltip.innerHTML` with interpolated child names / values. Child names are
  user-supplied and are injected without escaping. Replace with `textContent`
  or Lit templating.
- **Silent promise rejections** in `taskmate-parent-dashboard-card.js:620-685`
  and `taskmate-rewards-card.js:897-907` — service-call errors are
  console-logged only; the user sees no indication the action failed.
- **Leaking interval** in `taskmate-config-sounds.js:592` —
  `setInterval(findAndEnhanceSoundSelectors, 2000)` has no cleanup. Combined
  with the live `MutationObserver`, both run until the tab closes.
- **Fragile DOM traversal**: `taskmate-reorder-card.js:790` chains
  `.closest(".chore-item")` without null-guarding the result.

### Dead / unused
- `SERVICE_RESET_DAILY` (as above).
- `models.py:12` truncates `uuid4().hex` to 16 chars with no comment — intent
  unclear and collision-risky at scale.
- Cards assign `this._celebrating = null` etc. in constructors but don't
  declare them in `static get properties()`; changes won't trigger renders.

## 2. Cross-browser & Responsiveness

- Responsive breakpoints cluster around 380 / 400 / 480 / 600 / 1023 px across
  all cards — **no ≥ 1200 px breakpoint**. Widescreen layouts look sparse.
- No explicit tablet (768 px) breakpoint; portrait tablets fall back to
  mobile.
- Hard-coded pixel widths in several card headers (e.g.
  `taskmate-child-card.js`, `taskmate-parent-dashboard-card.js`) cause
  overflow on 320-px devices.
- No vendor prefixes for `-webkit-backdrop-filter` in glass-style panels —
  Safari < 18 loses the blur.

## 3. UI / UX

- Most buttons have `:hover` but no `:focus-visible` styles — keyboard users
  get no visible focus ring.
- Click handlers (`@click`) rarely paired with `@keydown.enter` /
  `@keydown.space`, so non-button elements acting as buttons aren't keyboard
  operable.
- Optimistic-completion loading state in `taskmate-child-card.js:1767`
  updates visually only after `requestUpdate()`; there's a flicker window
  where the button accepts a second click.
- Error states lack user-visible feedback (see §1). Add a shared toast /
  snackbar so every service failure surfaces the same way.
- Spacing and typography are inconsistent between the older cards (overview,
  weekly, streak) and newer ones (bonuses, points-display). Harmonise to one
  type scale + spacing ramp.

## 4. Restyling Suggestions

- The overview, weekly, and leaderboard cards use heavy drop-shadows and
  saturated accent colours — feels early-Material. Newer cards (bonuses,
  parent-dashboard) lean flatter. Pick one style, apply globally.
- Replace ad-hoc gradient headers with a single CSS custom-property theme
  (`--tm-bg`, `--tm-bg-elev`, `--tm-accent`) respected by all cards. Today
  each card re-declares its palette.
- Typography: mixing 14/15/16 px base sizes across cards. Standardise on
  14 px body / 13 px caption / 20 px heading.
- Icon sizing is inconsistent (16 / 20 / 24 px). Lock to two sizes (20 for
  inline, 24 for action buttons).

## 5. Performance

- `taskmate-child-card.js` = 75 KB and contains the entire Web-Audio sound
  synthesis routine — duplicated again in `taskmate-config-sounds.js` (~21 KB
  of that). Extract to `taskmate-sounds.js`, lazy-import when needed.
- `images/` is 2.0 MB — `rewardCard.png` (370 KB), `editChores.png` (187 KB),
  `streak.png` (161 KB), `leaderboardCard.png` (146 KB). Run `oxipng -o4`;
  30–50 % savings is typical without quality loss.
- README references images via `github.com/.../blob/main/...` URLs, which
  render slowly. Switch to `raw.githubusercontent.com`.
- 10 fart MP3s (~400 KB) loaded eagerly if `fart_random` is ever resolved in
  advance. Confirm loading is lazy (`new Audio(url)` on play only).
- Every card runs a `document.querySelectorAll('script[src*=".../taskmate-X-card.js"]')`
  at module load to recover a version string. 18× DOM scans at page load.
  Read once and share.
- Animated elements (confetti, mode-toggle transitions) have no `will-change`
  hint; the compositor promotes them late.

## 6. Accessibility

- Icon-only buttons (approve `mdi-check`, reject `mdi-close`, drag handles,
  etc.) have no `aria-label`. Screen readers announce "button" with no
  context.
- Images in cards that serve a purpose (avatars, reward thumbnails) have no
  `alt`. Decorative images should have `alt=""` explicitly.
- Colour contrast for grey secondary text (`#888` on white) fails WCAG AA.
- `tabindex` is not set on custom draggable items in
  `taskmate-reorder-card.js`; keyboard users can't reorder.
- No `aria-live` region for the toast / status messages that do exist; screen
  readers miss them.

## 7. Code Quality / Security / SEO

- **XSS** in `taskmate-graph-card.js` (see §1) — the only clear security
  finding.
- `except Exception: pass` in `config_flow.py:116, 140-154` swallows
  translation-loading errors silently.
- Type hints missing on public storage methods (`get_children`, `get_chores`,
  …). `coordinator.py:33` uses builtin `callable` for a type annotation
  instead of `typing.Callable`.
- No linting workflow in CI — only `hassfest` and `pytest` run. Add
  `ruff`/`black` (Python) and `eslint`/`prettier` (JS).
- Duplicate translation source directories (`translation_files/` vs
  `custom_components/taskmate/translations/`). The former is stale
  (EN + FR only) and will drift. Delete or mark canonical.
- `hacs.json` claims HA ≥ `2024.1.0`; README badge claims `2025.1+`.
  Reconcile.
- `.github/.DS_Store` is committed — remove with `git rm --cached` and ensure
  `.gitignore` covers it (it does globally, but the file was added before).
- Issue templates reference the now-deleted `docs/wiki` (commit `0d33810`).
- README lacks a browser-requirements section, a prominent privacy
  statement, and a changelog link in the header — all useful for SEO and
  discoverability on HACS.
- No meta description / OG tags in README for GitHub previews.
- Tests: no coverage for `config_flow.py`, service registration in
  `__init__.py`, or platform setup. Service-schema drift won't be caught.

---

## Prioritised Fix List

### Critical — ship first
1. **Escape user data in graph tooltip** — replace `tooltip.innerHTML =` with
   `textContent` or Lit templating. `taskmate-graph-card.js:527`.
2. **Register `SERVICE_RESET_DAILY`** (or remove the constant). `const.py:200`,
   `__init__.py:_async_register_services`.
3. **Await `hass.bus.async_fire`** in `handle_preview_sound`. `__init__.py:223`.
4. **Surface service-call errors** to the user in parent dashboard & rewards
   cards (shared toast component). `taskmate-parent-dashboard-card.js:620-685`,
   `taskmate-rewards-card.js:897-907`.
5. **Fix the `setInterval` leak** in `taskmate-config-sounds.js:592` — clear
   interval on disconnect / unload.
6. **Remove `.github/.DS_Store`** from the repo.

### Should Fix — next release
7. Harden the dynamic `__getattr__` routing in `TaskMateOptionsFlow` — pass
   the selected id as a flow argument instead of mutating `self`.
   `config_flow.py:1272-1289`.
8. Guard `self.coordinator` access against missing `hass.data[DOMAIN][entry_id]`.
9. Add `aria-label`s to every icon-only button; add `:focus-visible` rings
   globally.
10. Reconcile `hacs.json` minimum HA version with the README badge.
11. Delete / document `translation_files/`; make one directory canonical.
12. Update issue-template wiki links now that `docs/wiki` was removed.
13. Add a Python linting workflow (`ruff` + `black --check`) to `.github/workflows/`.
14. Compress `images/*.png` (`oxipng -o4`).
15. Rewrite README image URLs to `raw.githubusercontent.com/...`.
16. Extract the Web-Audio sound engine from `taskmate-child-card.js` and
   `taskmate-config-sounds.js` into a shared module.
17. Replace `except Exception: pass` in `config_flow.py:116, 140-154` with
   logged, specific handlers.
18. Add a ≥ 1200 px breakpoint and a 768 px tablet breakpoint to every card.
19. Add test coverage for `config_flow.py` and for service registration in
   `__init__.py`.
20. Fix `coordinator.py:33` type hint (`Callable` from `collections.abc`).
21. Declare all Lit reactive properties in `static get properties()`.

### Nice to Have — polish
22. Harmonise typography scale, spacing ramp, and icon sizes across all cards.
23. Introduce `--tm-*` CSS custom properties for theme tokens; remove per-card
   palettes.
24. Split `coordinator.py` (52 KB) by concern (completion, rewards, penalties,
   points).
25. Lazy-load fart MP3s only when the selected sound is requested.
26. Add `will-change` hints to confetti and mode-toggle animations.
27. Raise secondary-text contrast to WCAG AA.
28. Add an `aria-live="polite"` region for toast notifications.
29. Pin workflow actions to stable versions (`checkout@v4`,
   `setup-python@v5`) and add Dependabot for actions.
30. Expand README with Browser Requirements, Privacy callout, and a header
   link to CHANGELOG.
31. Document `models.py:12` id-truncation rationale or stop truncating.
32. Add a screenshot / section for the Penalties and Bonuses cards to the
   README.

---

*Generated: 2026-04-17.*
