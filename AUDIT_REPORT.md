# TaskMate — Comprehensive Codebase Audit

**Project:** `tempus2016/taskmate` — Home Assistant custom integration (family chore / points tracker)
**Audited revision:** `main` (manifest **v4.3.1**)
**Scope:** ~15k LOC Python (`custom_components/taskmate/`) + ~24k LOC JavaScript (23 LitElement cards + admin panel) + configs, CI, translations, 74 test files
**Mode:** Strictly read-only. No source files were edited and no code was executed. The only file written is this report (overwriting the previous stale report, which was generated at v3.9.6).

> **Verification note:** Findings were gathered by five parallel read-only domain agents (backend core / business logic / frontend group A / frontend group B / config-CI-i18n-tests), then **synthesised and spot-verified against source by hand**. Several fan-out claims were **overstated and have been downgraded on verification** — see *Appendix B: Corrections*. In particular the "timezone bucketing breaks streaks" claim is **mostly wrong** (a noon-anchor mitigation is present) and the `header_color` CSS-injection severity was reconciled between two agents.

---

## 1. Executive Summary

TaskMate is a **mature, well-hardened** integration. Since the v3.9.6 audit, **every previously-flagged High issue has been fixed** and verified at HEAD:

- **WS access control:** all ~69 websocket commands now carry `@_admin_only` (incl. every `ws_notif_*`); the panel is `require_admin=True`. `test_websocket_admin.py` asserts `ERR_UNAUTHORIZED` for non-admins.
- **Service access control:** mutating services go through `_async_require_admin`; child-self-service goes through `_async_require_linked_child`. Covered by `test_service_admin_gate.py` / `test_service_linked_child_gate.py`.
- **Double-award:** `async_approve_chore` now guards `if completion.approved: return` (`coord_chores.py:796`).
- **Overnight timed tasks:** midnight marker is tz-aware (`coord_timed.py:181`, `dt_util.start_of_local_day()`).
- **Photo proof** is a real feature now (`http_photos.py` / `photos.py`): auth-gated views, server-generated uuid filenames, strict `FILENAME_RE`, magic-byte sniffing, and `photo_url` rejected unless it passes `is_taskmate_photo_url` (matches the recent `9d86c47` fix).

**No Critical issues. No confirmed High issues remain after verification.** The substantive items are **Medium**, dominated by three themes:

1. **Front-end consistency gaps** — 7 cards interpolate `header_color` raw into `<style>` while the other 11 use the existing `_safeColor` sanitiser (CSS-injection, config-author-scoped); massive copy-paste (colour-picker block in **17 cards**, bonuses/penalties cards **~95% identical**).
2. **Reversal/recurrence correctness edges** — reject/undo does not reverse **streak-milestone** bonuses; availability vs calendar diverge when `recurrence_start` is unset; streak "pause-resume" misses today's +1.
3. **Scaling & coverage** — O(chores×children×completions) availability rebuild on every refresh; no JS lint in CI; `button.py` and the timed-task lifecycle untested; 7 services missing translation blocks in all 9 locales.

---

## 2. Methodology & Scope

Partitioned into five independent domains, analysed in parallel, then synthesised and verified by re-reading source:

| Domain | Files |
|---|---|
| Python backend core | `__init__.py`, `coordinator.py`, `storage.py`, `config_flow.py`, `panel.py`, `frontend.py`, `websocket.py`, `http_photos.py`, `photos.py` |
| Python business logic | `models.py`, `const.py`, `templates.py`, `sensor.py`, `binary_sensor.py`, `button.py`, `calendar.py`, all `coord_*.py` |
| Frontend A | `taskmate-panel.js`, `child`, `rewards`, `parent-dashboard`, `approvals`, `points`, `design`, `localize`, `attr-resolver` |
| Frontend B | remaining 14 `www/*.js` |
| Config/deps/CI/i18n/tests | `manifest.json`, `hacs.json`, `pyproject.toml`, `services.yaml`, `strings.json`, `translations/*`, `.github/workflows/*`, `tests/` |

Threat model: a self-hosted, family-scoped HA instance behind HA auth. The adversary is *other authenticated household members* (incl. a child login or a kiosk token), not anonymous internet access.

---

## 3. Findings by Category

### 3.1 Security

**SEC-1 — `header_color` interpolated unescaped into `<style>` in 7 cards *(Medium — VERIFIED)***
- **Files (raw, no `_safeColor`):** `taskmate-approvals-card.js:507`, `taskmate-parent-dashboard-card.js:525`, `taskmate-rewards-card.js:1185`, `taskmate-child-card.js:2004`, `taskmate-points-card.js:732`, `taskmate-badges-card.js:656`, `taskmate-points-display-card.js:773,873`.
- **Issue:** Lit does **not** escape inside `<style>`. A `header_color` like `red} :host{display:none} x{a:url(//evil` injects arbitrary CSS (content hiding / approve-button overlay spoofing / outbound `url()` exfil). The fix already exists in the repo — `_safeColor(c,d)` (`/^#[0-9a-fA-F]{3,8}$/`) is defined and applied in the **other 11** cards (activity, bonuses, penalties, calendar, graph, leaderboard, overview, reorder, reward-progress, streak, weekly). These 7 simply never adopted it. *(Verified: `grep _safeColor` returns 0 in all 7, ≥3 in the other 11.)*
- **Why Medium not High:** `header_color` is a Lovelace card-config key — settable only by someone who can edit dashboards; it's a bounded CSS context (no `</style><script>` breakout). Real but author-scoped.
- **Fix:** import/define `_safeColor` and wrap every `header_color` used inside a `<style>` block in the 7 cards. Best done once via the shared `taskmate-design.js` layer.

**SEC-2 — Photo upload accepts any authenticated user, no count/size quota *(Medium — VERIFIED)***
- **File:** `http_photos.py:37` (`TaskMatePhotoUploadView.post`).
- **Issue:** Upload is bearer-auth-gated (good) and per-file-capped at 8 MB (`photos.py:26`), but there is **no per-child/admin check and no quota** on file count or total disk. A logged-in non-admin or compromised child token can fill `<config>/taskmate_photos`. Orphaned uploads (never attached to a completion) are never swept — cleanup only runs when a completion is pruned/rejected (`coord_points.py:893`, `coord_chores.py:985`).
- **Fix:** tie uploads to a known child/session, add a count+size quota, and add a periodic sweep of unreferenced photos. See FEAT list.

**SEC-3 — Service mutations are not written to the admin audit log *(Medium — VERIFIED)***
- **Files:** service handlers in `__init__.py` vs the WS audit path (`websocket.py:230-242`, `coordinator.async_record_audit`).
- **Issue:** The panel/WS path records every mutating command; the equivalent **service** calls (`add_points`, `remove_points`, `gift_points`, `apply_penalty`, `complete_chore as_parent`, `add/remove_chore`, …) do not. An admin or automation can move points/apply penalties via Dev Tools with no audit trail, undermining the audit feature.
- **Fix:** route service mutations through `async_record_audit`, or document that only panel actions are audited.

**SEC-4 — `complete_chore` self-service is open per-child by default (kiosk impersonation) *(Medium — VERIFIED, partly by design)***
- **Files:** `__init__.py:346-373`, `_async_require_linked_child` (`310-329`).
- **Issue:** When a child has no `linked_user_id`, any authenticated user may complete chores for that `child_id` (intended kiosk behaviour). But the gate is opt-in *per child*, so in a mixed setup a linked child A can complete chores as an unlinked child B by passing B's id — and (per SEC-3) it isn't logged.
- **Fix:** when *any* child is linked, default unlinked children to deny-cross-child for non-admins, or document the kiosk trade-off; at minimum log self-service completions.

**SEC-5 — `config/import` replaces all state; inner records not re-validated *(Low — VERIFIED)***
- **Files:** `websocket.py:1917`, `coordinator.async_import_config`, `storage.import_data`. Admin-gated (acceptable). The payload is deep-copied in with only top-level type coercion; inner records (incl. `photo_url`) aren't re-validated, so a crafted backup can inject a `photo_url` bypassing `is_taskmate_photo_url` (that check runs only in `complete_chore`). Requires admin to import.
- **Fix:** normalise/validate records on import; have the panel render only `photo_url`s that pass `is_taskmate_photo_url`.

**SEC-6 — Coordinator-layer points methods lack sign guards *(Low — VERIFIED, defense-in-depth)*** — `async_add_points`/`async_remove_points` (`coord_points.py:234-286`) don't guard `points >= 0`. **Not currently exploitable** — every reachable caller validates (`cv.positive_int`, `vol.Range(min=1)`). Clamp at the coordinator layer so the invariant holds regardless of caller.

> **Confirmed clean (verified):** WS admin gating uniform across ~69 commands; panel `require_admin=True`; photo path-traversal impossible (uuid filenames + `FILENAME_RE` before any FS access, magic-byte sniffing); no `eval`/`new Function`/`unsafeHTML`; the single raw `innerHTML` (graph SVG `:525`) uses only internal palette/literal values; panel routes all user strings through `_esc` and restricts photo `href/src` via `_safePhotoUrl`; `yaml.safe_load`/explicit `from_dict` only, no `pickle`; no hardcoded secrets; WS/photo auth tokens mean no cookie-CSRF surface; double-submit guards present on the panel/approvals/points/dashboard/rewards/child point handlers.

### 3.2 Errors & Faulty Code

**ERR-1 — Reject/undo does not reverse streak-milestone bonuses *(Medium — VERIFIED)***
- **Files:** `_reverse_completion_awards` (`coord_chores.py:883-927`) vs `_award_points` (`coord_points.py:800-841`).
- **Issue:** A milestone bonus is added **directly** to `child.points`/`total_points_earned` (`coord_points.py:831-832`) and logged as a **separate** transaction; the value stored as `completion.points_awarded` (the returned `total_points`, `:871`) does **not** include it. Reversal subtracts only `completion.points_awarded`, so milestone bonuses survive a reject/undo. (Weekend multiplier *is* in `points_awarded`, so that part reverses correctly.) Not easily farmable on repeat — `streak_milestones_achieved` isn't reset, so the milestone won't re-award until the streak resets — but it is real points drift on legitimate rejects/undos.
- **Fix:** link milestone (and perfect-week) transactions to the completion and reverse them, or recompute and subtract the milestone delta in `_reverse_completion_awards`.

**ERR-2 — Availability vs calendar diverge when `recurrence_start` is unset *(Medium — VERIFIED)***
- **Files:** `coord_chores.py:1134-1189` (availability) vs `coord_calendar.py:169-198` (projection).
- **Issue:** For `every_2_days` and the month-based recurrences (`monthly`/`every_3_months`/`every_6_months`) **without** a `recurrence_start`, availability falls back to a rolling window-from-last-completion and reports the chore as due, but the calendar requires an anchor and returns `False` — so a genuinely-available chore **never appears on the calendar**. Even *with* `recurrence_start` the two engines use different models (window-from-completion vs fixed-anchor cadence) and disagree the day after an early/late completion. Also, the never-completed branch (`coord_chores.py:1134-1151`) returns `True` every day for month-based chores while the calendar shows only the anchor day.
- **Fix:** extract one shared `is_scheduled_on(chore, day)` predicate used by both availability and calendar (resolves ERR-2 and QUAL-1 together); or require `recurrence_start` for these recurrences at create time.

**ERR-3 — Streak "pause-resume" omits today's increment *(Medium — VERIFIED)***
- **File:** `coord_points.py:773-785`. On resume from a paused gap the branch clears `streak_paused` and updates `last_completion_date` but never does `current_streak = streak_before + 1` (unlike the consecutive-day branch). The qualifying completion that resumes the streak isn't counted → streak under-counts by one per pause cycle.
- **Fix:** set `child.current_streak = streak_before + 1` on resume.

**ERR-4 — `points-card` toast `setTimeout` not tracked/cleared *(Medium — VERIFIED pattern)***
- **File:** `taskmate-points-card.js:1193-1196` (`_showNotification`). The 3 s dismiss timer has no stored handle and isn't cleared in `disconnectedCallback` (`1118-1124`) → `requestUpdate()` on a detached element if the card is removed within 3 s; rapid actions stack timers and an older one can clear a newer toast early.
- **Fix:** store the handle; clear the prior timer on each call and on disconnect.

**ERR-5 — Double-submit on bonuses/penalties create & edit *(Medium — REPORTED)***
- **Files:** `taskmate-bonuses-card.js:529,559` and the near-identical `taskmate-penalties-card.js:529,559` (`_saveEdit`/`_saveNew`). The form closes only after the `await` resolves and the save button has no loading/disabled guard, so a fast double-click fires `add_bonus`/`update_bonus` (or penalty) twice → duplicate rows. (`_applyBonus`/`_applyPenalty` *are* guarded — use them as the template.)
- **Fix:** add a `_saving` flag + `?disabled`.

**ERR-6 — `config-sounds.js` MutationObserver never disconnected *(Low-Medium — VERIFIED)***
- **File:** `taskmate-config-sounds.js:571` (observer) + `:604` (10 s interval). `cleanup` (`:606-618`) clears the interval and debounce timer on `pagehide`/`beforeunload` but the body-subtree `MutationObserver` is created in a local `const` unreachable from `cleanup`, so it is never `.disconnect()`ed. In HA's SPA those unload events rarely fire, so a whole-`document.body` subtree observer effectively runs for the tab's life.
- **Fix:** hoist the observer to a module/window ref and `.disconnect()` it in `cleanup`; consider stopping after first successful enhancement.

**ERR-7 — Cosmetic timezone edges (date labels/countdown) *(Low — VERIFIED, DOWNGRADED)***
- **Files:** `taskmate-graph-card.js:910` (`new Date().toLocaleDateString("en-CA")` with no `timeZone` for the Today/Yesterday label); `taskmate-child-card.js:2949-2957` (`_getMidnightCountdown` builds `tomorrow` browser-local; `tomorrowUTC` computed but unused); various display-only `toLocaleTimeString` without `timeZone`.
- **Note:** The headline streak/weekly/graph **day-bucketing is NOT broken** — `today` is anchored to the HA-tz `todayKey` then `+"T12:00:00"` (noon) and walked back in whole days, so generated axis keys match the HA-tz completion buckets even when browser TZ ≠ HA TZ. Only labels/countdowns are affected. *(See Appendix B.)*
- **Fix:** pass `{ timeZone: tz }` to the label `toLocaleDateString`/`toLocaleTimeString` calls.

**ERR-8 — Child-card badge subscribe double-in-flight *(Low — VERIFIED)*** — `taskmate-child-card.js:111-130`: the post-await `isConnected` guard and `disconnectedCallback` unsub are correct, but the top guard checks `_badgeEventUnsub` which is still null mid-subscribe, so a fast disconnect→reconnect can start a 2nd subscribe that orphans the 1st. (badges-card itself is done correctly via `_subscribing`.) Add an `_subscribing` in-flight flag.

**ERR-9 — Misc smaller items *(Low)***
- `storage.set_setting` typed `value: str` (`storage.py:1133`) but stores lists/floats/bools; `get_setting -> str` causes float-as-string round-tripping (`coordinator.py:82-88`). Type as `Any`.
- `coord_timed._calc_session_seconds` (`:156-158`) would `TypeError` on a *legacy naive* stored segment (silently skipped → lost time); current writers store aware ISO. Normalise via `dt_util.parse_datetime`.
- `taskmate-approvals-card.js` uses `--mdi-icon-size` (typo for `--mdc-icon-size`) — ineffective CSS.
- Read-modify-write on shared records is last-write-wins (no lock); `async_gift_points` reads both balances then awaits save — a concurrent `add_points` between read and save is clobbered. HA's single-threaded loop bounds this to await-interleavings (two kiosks). Consider an `asyncio.Lock` around read-modify-write+save.

### 3.3 Dead & Unused Code

- `taskmate-rewards-card.js:484-499` — dead CSS for `.reward-row.dynamic`/`.dynamic-cost`/`.dynamic-indicator`; dynamic/surge pricing was deliberately removed (`_getDisplayCost:1718` "costs are static"). Safe to delete.
- `taskmate-child-card.js:2949` — `tomorrowUTC` computed, never used.
- `STORAGE_VERSION = 1` (`storage.py:21`) never bumped despite many ad-hoc in-`_data` migration flags — `Store`'s migration hook is unused. Architectural note, not a bug.
- `_get_coordinator` defined twice with different semantics (`__init__.py:206`, `websocket.py:202`) — both correct; mild DRY.

### 3.4 Code Quality & Improvements

- **QUAL-1** *(Medium — VERIFIED)* — recurrence math duplicated/divergent across `coord_chores.py:1056-1189` and `coord_calendar.py:156-198` (root of ERR-2); the weekday `day_map` appears 3× and the month-steps map 2× in `coord_chores.py` (a 4th copy lives in the calendar card). Extract one shared `is_scheduled_on(chore, day)` predicate + module-level `_DOW_MAP`.
- **QUAL-2** *(Medium — VERIFIED by diff)* — `bonuses-card.js` and `penalties-card.js` are **~95% identical** (~1050 lines each; the entire diff reduces to name/colour/icon/service-prefix/i18n-prefix). Every fix (e.g. ERR-5) must be made twice. Extract one component parameterised by `{kind, colour, icon, servicePrefix, i18nPrefix}`.
- **QUAL-3** *(Medium — VERIFIED by grep)* — the colour-picker editor (`_renderColourPicker` ~30 lines + `.colour-*` CSS ~13 lines) is copy-pasted into **17 cards** (~730 lines of duplication; each file has exactly 19 `colour-` references). Factor into the shared `taskmate-design.js` layer (and fold in `_safeColor` from SEC-1).
- **QUAL-4** *(Low)* — `is_chore_available_for_child` is ~130 lines mixing vacation/enable/assignment/visibility/recurrence concerns; decompose into testable helpers (gates vs recurrence-due), sharing the recurrence check with the calendar (QUAL-1).
- **QUAL-5** *(Low)* — pervasive defensive `getattr(chore/child, 'field', default)` on always-present dataclass fields (48× in `coord_chores.py`, 24× in `coord_assignments.py`); masks typos and defeats type checking.
- **QUAL-6** *(Low)* — minimal Ruff rule set (`E/F/W` only, `pyproject.toml:7`); enabling `I` (isort) and `B` (bugbear) is low-cost. `_t()`/Lit boilerplate duplicated per card — a `taskmate-base.js` mixin would remove it (no build step).

### 3.5 Performance

- **PERF-1** *(Medium — VERIFIED)* — availability matrix is **O(chores × children × completions)**: `sensor._build_chore_availability` (`:285-299`) calls `is_chore_available_for_child` per chore×child; for rotation modes `_is_rotation_done_today` (`coord_chores.py:1090`) does a full `get_completions()` scan each time; `balanced` re-scans `get_chores()` per call (→ O(chores²×children)). Rebuilds on every refresh. **Fix:** compute today's completions-by-chore and rotation assignments once per refresh and pass them in; memoise per data-version.
- **PERF-2** *(Medium — VERIFIED)* — `_async_update_data` (`coordinator.py:457-476`) re-`from_dict`s every child/chore/completion every 30 s (`update_interval`), and `_build_state_snapshot` (`websocket.py:261-323`) shallow-copies all collections per `get_state`. **Fix:** consider event-driven refresh (mutations already `async_refresh()`); cache the snapshot keyed by a data-version counter.
- **PERF-3** *(Medium — VERIFIED)* — `storage.async_save` (`:247`) serialises the whole `_data` on every mutation, and some flows save 2-4× per operation. **Fix:** batch saves within one operation; consider `Store.async_delay_save` for hot paths.
- **PERF-4** *(Low — VERIFIED)* — `_async_update_service_descriptions` (`__init__.py:236-273`) hydrates all dynamic-selector options (re-`from_dict`-ing entities) and `repr()`s them as a change fingerprint on every listener fire *before* the short-circuit; deep-copies each affected description on change. Compute a cheaper fingerprint (ids+counts).
- **PERF-5** *(Low)* — `_audit_target` (`websocket.py:178-199`) does an O(n) `get_chore/get_child/get_reward` scan per audited command just to resolve a display name. Pass the already-resolved name.

### 3.6 Architecture & Maintainability

- **ARCH-1** *(Low — VERIFIED)* — direct `storage._data[...]` access bypasses the public `.data` property in several places (`__init__.py:133,138`; `coordinator.py:222-224,471`) for `_initial_setup_done`, `badges_backfill_pending`, `settings`. Add typed accessors so migrations/defaults can't drift.
- **ARCH-2** *(Low)* — `manifest.json:17` `iot_class:"calculated"` is now accurate (was the old `local_polling` gripe). Good.

### 3.7 CI / Supply Chain / Packaging

- **CI-1** *(Low — VERIFIED)* — `tests.yml:45` installs **unpinned** `pytest pytest-homeassistant-custom-component`, and references `requirements_test.txt`/`requirements.txt` that **do not exist**. A breaking harness release can red/green-flip CI independent of code. Pin the harness (ideally a real `requirements_test.txt`). Contrast `lint.yml:32` which correctly pins `ruff==0.15.12`.
- **CI-2** *(Low — VERIFIED)* — `home-assistant/actions/hassfest` and `hacs/action` are **SHA-pinned** (safe) but track upstream `master`/`main` (no version tags → manual bump cadence). Acceptable; consider Dependabot `github-actions`.
- **CI-3** *(Medium — VERIFIED)* — **no JS lint/format in CI** over the 23 `www/*.js` files (no `.eslintrc`/`package.json`/`.prettierrc` anywhere). The entire user-facing front-end has zero static-analysis gate; syntax errors surface only via manual ha-dev testing. Add ESLint (even `eslint:recommended`) + Prettier as a CI job.
- **GOOD (verified):** all third-party actions SHA-pinned; per-workflow least-privilege `permissions:`; `pull_request_target` (labeler) does **not** check out PR code — safe; only `GITHUB_TOKEN` referenced, no custom PATs; `release-zip.yml` attaches `taskmate.zip` to every published release (incl. pre-releases, required by the HACS `zip_release` rollout) with a manifest-at-root guard; `.gitignore` covers `__pycache__`/`.ruff_cache`/`.tmp`/`.claude` and none are tracked.

### 3.8 i18n / Documentation

- **I18N-1** *(Medium — VERIFIED count)* — `services.yaml` defines **44** services but `strings.json` + all 8 translation files contain only **37** service blocks. Missing from **every** locale: `apply_mandatory_penalty`, `choose_avatar`, `dismiss_mandatory_chore`, `gift_points`, `postpone_mandatory_chore`, `request_swap`, `test_notification`. They work (services.yaml fallback) but Dev Tools shows raw keys. Back-fill all 7 into `strings.json` then propagate to de/fr/nb/nn/pt/pt-BR (and en/en-GB). *(Matches your "translate new strings as part of the feature" rule — these slipped through.)*
- **I18N-2** *(Low — VERIFIED)* — translations carry a `selector/assignment_mode/options/first_come` key absent from `strings.json` (546 vs 545 keys). Since `first_come` is a live assignment mode, **add it back to `strings.json`** (source of truth).
- **DOC** — README (1,000+ lines) documents the full service surface, scheduling, badges, quests, challenges, pool mode, and every card. Strong. Note: the admin **panel** UI strings live in `www/` JS, outside the HA i18n system — a separate effort if a multilingual panel is ever wanted.

### 3.9 Tests / Coverage

74 `test_*.py` files; most `coord_*` modules are exercised transitively via the `TaskMateCoordinator` facade. Gaps:

- **TEST-1** *(Medium — VERIFIED)* — `button.py` (251 LOC) is **completely untested** (no test imports it). Largest untested module. Add entity-setup + press→service tests.
- **TEST-2** *(Medium — VERIFIED)* — the timed-task lifecycle (`start/pause/stop_timed_task`, `coord_timed.py`) has **no direct test**. Add `test_timed_task.py` covering start/pause/stop and the overnight-close path (would lock in the ERR-1-class regression protection).
- **TEST-3** *(Low — VERIFIED)* — `config_flow.py`, `panel.py`, `http_photos.py` untested. `http_photos.py` is an access-control surface (auth + traversal) worth a view test; a standard `MockConfigEntry` flow test is cheap.
- **Note:** memory `project_test_suite_pollution.md` records a full-suite ordering instability (passes individually). Diff failure sets against `main`, don't expect a clean full run.

| Area | Tested? |
|---|---|
| WS admin gate / service admin gate / linked-child gate | yes (dedicated) |
| chores / points / rewards / assignments / badges / mandatory / quests / challenges / avatars / calendar / photos / notifications | yes |
| sensor / storage / models / coordinator | yes |
| `button.py` | **no** |
| timed-task services (`coord_timed.py`) | **no direct** |
| `config_flow.py` / `panel.py` / `http_photos.py` | **no** |
| `www/*.js` (~24k) | none (no JS test/lint harness) |

---

## 4. Prioritised Action List

**Do first (low effort, real correctness/security value):**
1. **SEC-1** — apply the existing `_safeColor` to `header_color` in the 7 cards.
2. **ERR-1** — reverse streak-milestone bonuses on reject/undo.
3. **ERR-3** — add the missing `+1` on streak pause-resume.
4. **ERR-4 / ERR-5** — track+clear the points-card toast timer; add save guards to bonuses/penalties create/edit.
5. **I18N-1/I18N-2** — back-fill the 7 missing service translations + the `first_come` selector key.

**Next (Medium):**
6. **ERR-2 / QUAL-1** — one shared `is_scheduled_on()` predicate; fixes availability-vs-calendar divergence and the unset-`recurrence_start` cases.
7. **SEC-2 / SEC-3 / SEC-4** — photo quota + orphan sweep; audit-log service mutations; tighten kiosk cross-child completion.
8. **PERF-1** — precompute the availability matrix inputs once per refresh.
9. **CI-3** — add ESLint/Prettier over `www/` in CI.
10. **QUAL-2 / QUAL-3** — merge bonuses/penalties; extract the colour-picker into `taskmate-design.js`.
11. **TEST-1 / TEST-2** — tests for `button.py` and the timed-task lifecycle.

**Then (Low):** PERF-2/3/4/5; ERR-6/7/8/9; SEC-5/6; CI-1/2; ARCH-1; dead-code removal (3.3); Ruff `I`+`B`.

---

## 5. Suggested New Features

Each verified **absent** at HEAD (grepped models/const/platforms — no field, const, or platform). Marked S/M/L effort.

1. **FEAT-1 — Chore dependencies / unlocks** *(M)* — chore B becomes available only after chore A is approved. No `depend/unlock/prereq` field exists today; fits the task-group model. Implement via the shared scheduling predicate from QUAL-1.
2. **FEAT-2 — Leaderboard "seasons"** *(M)* — monthly reset + champion badge so a perpetual leader doesn't demoralise siblings. Zero `season` references exist.
3. **FEAT-3 — Allowance / real-money payout log** *(M)* — convert points to a parent-confirmable weekly allowance with a payout ledger. **Fixed-cost only — no dynamic pricing** (per project rule). (`claim_allowance_minutes` is an unrelated grace window.)
4. **FEAT-4 — Family / shared co-op goals** *(M)* — a shared target ("everyone hits 500 → family movie night") with a progress card; extends Pool Mode. No `family_goal/shared_goal` exists.
5. **FEAT-5 — Per-child quiet hours / DND** *(S-M)* — suppress reminders during school/bedtime; complements notification routing. No `quiet`/`dnd` logic exists.
6. **FEAT-6 — Reminder escalation** *(S-M)* — nudge → reminder → parent alert if a mandatory chore stays incomplete. No `escalat` logic exists.
7. **FEAT-7 — Explicit negative-balance policy** *(S)* — `allow_negative` / floor-at-zero setting + UI when a penalty would push a child below zero. No such flag exists.
8. **FEAT-8 — Native `todo` platform** *(M)* — expose each child's due chores as a HA To-do list (unlocks the native to-do card + voice assistants for free). `PLATFORMS` is currently SENSOR/BUTTON/BINARY_SENSOR/CALENDAR only.
9. **FEAT-9 — `number`/`select` config entities** *(S)* — expose key settings (multipliers, costs) as entities so they're automatable without service calls.
10. **FEAT-10 — ICS / calendar subscription export** *(M)* — a subscribe URL so chores show in Google/Apple Calendar. No `ics/ical` in `calendar.py`.
11. **FEAT-11 — Automation blueprint pack** *(M)* — ship official blueprints ("on chore approved → flash a light", "bedtime → lock rewards"). No `blueprints/` dir.
12. **FEAT-12 — Voice intents** *(M)* — register HA conversation intents ("did Malia finish her chores?"). No intent registration today.
13. **FEAT-13 — Photo-proof gallery + quota** *(S)* — now that `http_photos.py` stores proofs, add a history/gallery card and the orphan-sweep/quota from SEC-2.
14. **FEAT-14 — Monthly "report card" summary** *(M)* — per-child monthly recap (weekly digest already exists).

> **Already implemented — do NOT re-propose:** export/import (`config_backup`), undo (`undo_transaction`/`undo_chore_approval`), photo proof (`http_photos.py`), chore swap (`request_swap`), claim-first marketplace (`first_come` assignment mode), availability-based streak freeze (`pause_streak_when_unavailable`), gift points, levels, interest, points decay, spend cap, quests, challenges, avatars, badges, timed tasks, task groups, pool/savings mode.

---

## Appendix A — Status of the v3.9.6 audit's High items (all fixed)

| Old finding | Status at v4.3.1 | Evidence |
|---|---|---|
| SEC-1 `ws_notif_*` missing admin gate | **Fixed** | all ~69 WS cmds `@_admin_only`; `test_websocket_admin.py` |
| SEC-3 service layer not admin-gated | **Fixed** | `_async_require_admin` + `test_service_admin_gate.py` |
| ERR-2 approve double-award | **Fixed** | `coord_chores.py:796` `if completion.approved: return` |
| ERR-1 overnight timed loss | **Fixed** | `coord_timed.py:181` `start_of_local_day()` |
| FEAT export/import, photo proof, undo | **Shipped** | `config_backup`, `http_photos.py`, `undo_*` |

## Appendix B — Corrections (fan-out claims rejected/downgraded on verification)

1. **"Timezone bucketing breaks streaks/weekly/graph (HIGH)"** — **DOWNGRADED to Low (cosmetic).** Verified: `today` is anchored to the HA-tz `todayKey` then `+"T12:00:00"` and walked back in whole days, so axis keys match the HA-tz completion buckets even when browser TZ ≠ HA TZ. Only the graph Today/Yesterday label (`:910`) and child-card countdown are browser-local. (`streak-card.js:386-391`, `weekly-card.js:695-713`, `graph-card.js:812-815`.)
2. **`header_color` CSS-injection severity** — two agents disagreed (HIGH vs MEDIUM) and on the file count. Reconciled: **7 cards** unsanitized (not 5, not 2), **Medium** (config-author-scoped, bounded CSS context).
3. **"badges-card subscription leak (HIGH)"** — **rejected.** badges-card handles the connect/disconnect race correctly (`_subscribing` + post-await `isConnected` guard + `disconnectedCallback` unsub). The real (minor) gap is the *child-card* in-flight guard → ERR-8 (Low).
4. **"graph full-canvas redraw every update (perf)"** — **rejected.** `shouldUpdate` gates on `window.__taskmate_hasChanged`; redraw fires only on relevant entity change.
5. **ERR-1 framed as "farm milestones repeatedly"** — **scoped down:** `streak_milestones_achieved` isn't reset, so re-farming needs a full streak reset; the real bug is points drift on legitimate reject/undo → **Medium**.

---

*End of report. No fixes were applied; all items are described only. No state was modified during this audit.*
