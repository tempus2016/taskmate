# TaskMate v1.0.5

## What's New

This is a major feature release adding 8 new Lovelace cards, a complete reward approval flow, streak tracking, activity history, points graph, and significant improvements to the parent dashboard experience.

---

## 🆕 New Cards

### Parent Dashboard Card
A unified parent control centre replacing the need for multiple separate cards. Four tabs in one card:
- **Overview** — all children's today chore progress with points
- **Approvals** — pending chore completions with inline approve/reject buttons
- **Claims** — pending reward claims with approve/reject (see reward approval flow below)
- **Points** — quick +/- buttons per child with configurable step amount

### Reward Progress Card
A full-screen motivational display designed for wall tablets. Shows a single reward's progress with an animated progress bar, floating reward icon, and a pulsing "Ready to claim!" badge when the child can afford it. Supports jackpot rewards with combined pool view.

### Leaderboard Card
Ranks all children competitively by all-time points, current streak, or this week's points — configurable in the editor. Top 3 get gold/silver/bronze styling. For single-child households, automatically switches to a personal bests display showing best streak, total chores, weekly points, and total earned.

### Activity Card
A scrollable timeline of all activity including chore completions, manual point adjustments, and reward claim events. Groups by Today / Yesterday / date. Filterable by child with configurable item limit.

### Overview Card
At-a-glance parent summary showing every child's today chore progress bar, points, pending approval chip, and footer totals. Pulsing red badge when approvals are pending.

### Streak Card
Per-child streak display with dot history, current and best streak, and achievement badges (First!, 3/7/14/30 day streaks, 10/50/100 chores, 50/100 points). Uses backend-tracked streaks for accuracy.

### Weekly Card
Mon–Sun week view with daily bar chart, headline stats (chores, points, days active), and per-child breakdown. All stats correctly filter to approved completions only.

### Points Graph Card
Canvas-based line graph tracking daily or cumulative points over a configurable date range (3–90 days). Supports multiple children with colour-coded lines. Hover/touch tooltip shows values per day.

---

## ✅ Reward Approval Flow

Reward claiming is now a two-step process matching the existing chore approval pattern:

1. Child taps **Claim** on the rewards card → creates a pending claim, points are **not deducted**
2. Parent sees the claim in the **Claims tab** of the Parent Dashboard with Approve ✓ / Reject ✗ buttons
3. **Approve** → points deducted, reward granted
4. **Reject** → claim deleted, no points affected

This prevents children from instantly redeeming rewards without parental oversight. The `approve_reward` service now handles point deduction. A new `reject_reward` service is also registered.

> **Note:** Existing reward claims made before this update had points deducted immediately under the old behaviour. Only new claims follow the two-step flow.

---

## 🔥 Streak Tracking

Streaks are now properly tracked and maintained by the backend:

- **Automatic midnight check** — every night at 00:00:05 the coordinator checks each child's last completion date and updates streaks accordingly
- **Two configurable modes** (Settings → Integrations → TaskMate → Configure → Settings):
  - **Reset** (default) — streak goes to 0 on a missed day
  - **Pause** — streak is preserved and resumes from where it left off on the next completion
- `current_streak`, `best_streak`, `last_completion_date` all exposed in the sensor

---

## 📜 Activity History & Points Transactions

All manual point adjustments (add/remove) are now logged as `PointsTransaction` records and appear in the Activity Card feed alongside chore completions and reward claim events. Capped at 200 entries in storage.

---

## 🗂️ History Pruning

Completion history is now automatically pruned daily at 00:01:00. Configurable retention period (30–365 days, default 90) in Settings → Integrations → TaskMate → Configure → Settings. Pending (unapproved) completions are always retained regardless of age.

---

## 📅 Chore Scheduling (due_days)

The `due_days` field on chores is now respected by the child card. Configure per-card behaviour in the card editor:
- **Hide** — chores not scheduled for today are hidden entirely
- **Dim** — shown greyed out and non-interactive
- **Show** — shown normally regardless of schedule

---

## 🌙 Dark Mode

The child card now fully supports HA dark themes. All hardcoded white/grey colours replaced with CSS variables (`--card-background-color`, `--primary-text-color`, `--divider-color`).

---

## ⏱️ Reset Countdown

The child card can optionally show a countdown to midnight beside the "Today's Chores" heading. Turns orange when under 1 hour. Toggleable in the card editor.

---

## 🛠️ Integration Settings

New options in Settings → Integrations → TaskMate → Configure → Settings:
- **Streak Reset Mode** — Reset or Pause
- **History Days to Keep** — 30 to 365 days (default 90)

---

## 🔧 Backend Improvements

- **`settings` storage** — generic key/value store for integration-wide settings without requiring new top-level storage fields
- **`committed_points` per child** — points reserved by pending reward claims exposed in sensor, used by rewards card to prevent over-claiming
- **`pending_reward_claims` sensor attribute** — full enriched list of pending reward claims with child name, reward name, cost, and timestamp
- **`today_day_of_week` sensor attribute** — current day in HA timezone for frontend due_days filtering
- **`recent_completions` increased to 200** — was 50
- **CALC_COSTS log spam fixed** — four `_LOGGER.warning` calls for reward cost calculation changed to `_LOGGER.debug`
- **`async_shutdown`** — coordinator now properly cancels scheduled listeners on unload

---

## 🔒 Safe Resource Registration

Fixed a critical issue where HA restarts could wipe all Lovelace resources from other integrations. Auto-registration now runs **only once on first install** and never again. A `resources_registered` flag is persisted in the config entry data. On all subsequent restarts, resource management is completely skipped.

> **Existing users:** On first restart with this version, missing TaskMate resources will be automatically re-added. After that, the flag is set and HA will never touch your resources again.

---

## 🐛 Bug Fixes

- Fixed duplicate `override_point_value` key in rewards sensor attributes
- Fixed `ha-combo-box` value binding in all card editors — replaced with native `<select>` elements that work reliably
- Fixed checkbox bindings in card editors — switched from `.checked` property binding to `?checked` attribute binding
- Fixed SVG rendering in points graph on mobile app — switched from SVG/innerHTML to Canvas 2D API
- Fixed streak card `_getAchievements` missing `entity_ref` parameter causing blank render
- Fixed weekly card counting unapproved completions toward points, chores, and days active stats
- Fixed overview card counting unapproved completions toward progress bar and "Done Today"
- Fixed parent dashboard Approvals tab badge showing combined chore + reward count instead of chores only

---

## 📦 New Files

| File | Type |
|------|------|
| `www/taskmate-overview-card.js` | New card |
| `www/taskmate-activity-card.js` | New card |
| `www/taskmate-streak-card.js` | New card |
| `www/taskmate-weekly-card.js` | New card |
| `www/taskmate-graph-card.js` | New card |
| `www/taskmate-reward-progress-card.js` | New card |
| `www/taskmate-leaderboard-card.js` | New card |
| `www/taskmate-parent-dashboard-card.js` | New card |

---

## ⚠️ Breaking Changes

- **Reward claiming is no longer instant** — claims now require parent approval before points are deducted. Children will see "Awaiting parent approval" after claiming. Parents must approve via the Parent Dashboard Claims tab or the `approve_reward` service.
- The `reject_reward` service has been added to `services.yaml` and `strings.json` — update both files.
- `const.py` has a new `SERVICE_REJECT_REWARD` constant.

---

## 📋 Files Changed

`__init__.py` · `coordinator.py` · `sensor.py` · `models.py` · `storage.py` · `config_flow.py` · `frontend.py` · `const.py` · `services.yaml` · `strings.json` · `translations/en.json` · `www/taskmate-child-card.js` · `www/taskmate-rewards-card.js` · `www/taskmate-points-card.js` · `www/taskmate-reorder-card.js` + 8 new card files
