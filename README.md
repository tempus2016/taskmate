<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/logo.svg" alt="TaskMate" width="180">
</p>
 
<h1 align="center">TaskMate</h1>
 
<p align="center">
  <strong>Turn chores into a game your kids actually want to play.</strong><br>
  A Home Assistant integration for family chore management, smart rewards, and streak tracking.
</p>
 
<p align="center">
  <a href="https://github.com/tempus2016/taskmate/releases"><img src="https://img.shields.io/github/v/release/tempus2016/taskmate" alt="Latest Release"></a>
  <a href="https://github.com/hacs/default"><img src="https://img.shields.io/badge/HACS-Default-41BDF5.svg" alt="HACS Default"></a>
  <a href="https://github.com/tempus2016/taskmate/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.1+-blue" alt="HA Version">
  <a href="https://github.com/tempus2016/taskmate/releases"><img src="https://img.shields.io/github/downloads/tempus2016/taskmate/total" alt="Downloads"></a>
</p>

<p align="center">
  <a href="https://github.com/tempus2016/taskmate/actions/workflows/validate.yml"><img src="https://github.com/tempus2016/taskmate/actions/workflows/validate.yml/badge.svg" alt="HACS Validation"></a>
  <a href="https://github.com/tempus2016/taskmate/actions/workflows/hassfest.yaml"><img src="https://github.com/tempus2016/taskmate/actions/workflows/hassfest.yaml/badge.svg" alt="hassfest"></a>
  <a href="https://github.com/tempus2016/taskmate/actions/workflows/tests.yml"><img src="https://github.com/tempus2016/taskmate/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/tempus2016/taskmate/actions/workflows/lint.yml"><img src="https://github.com/tempus2016/taskmate/actions/workflows/lint.yml/badge.svg" alt="Lint"></a>
</p>
 
> Originally created by [vinnybad/choremander](https://github.com/vinnybad/choremander). This fork adds 15 Lovelace cards, a bonus points system, streak tracking, reward approval flow, a penalty system, and much more.
 
---
 
## Contents
 
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Setup](#setup)
- [Chores & Rewards](#chores--rewards)
- [Chore Scheduling](#chore-scheduling)
- [Dynamic Chore Visibility](#dynamic-chore-visibility)
- [Bonus Points System](#bonus-points-system)
- [Notifications](#notifications)
- [Penalties](#penalties)
- [Achievement Badges](#achievement-badges)
- [Timed Tasks](#timed-tasks)
- [Task Groups](#task-groups)
- [Quests](#quests)
- [Challenges](#challenges)
- [Pool Mode (Savings Jars)](#pool-mode-savings-jars)
- [Dashboard Cards](#dashboard-cards)
- [Services](#services)
- [Jackpot Rewards](#jackpot-rewards)
- [Completion Sounds](#completion-sounds)
- [Finding IDs](#finding-ids)
- [Troubleshooting](#troubleshooting)
- [Tips](#tips)
 
---
 
## How It Works
 
1. **Create chores** — assign them to children, set point values and schedules
2. **Kids complete chores** — tap on the child card to tick off chores, earn points, build streaks
3. **Parents approve** — chores set to "requires approval" go into a pending queue
4. **Kids claim rewards** — when they have enough points, they claim a reward
5. **Parents approve claims** — points are only deducted once a parent approves
6. **Bonus points** — weekend multipliers, streak milestones, and perfect week bonuses add extra motivation
 
All data is stored locally in Home Assistant. Nothing leaves your instance.
 
---
 
## Installation
 
### Via HACS (Recommended)
 
TaskMate is a **default HACS integration** — no custom repository needed:
 
1. Open **HACS** → search **"TaskMate"**
2. Click **Download**
3. **Restart Home Assistant**
4. Add the integration: **Settings → Devices & Services → Add Integration → TaskMate**
 
Or use the one-click buttons:
 
[![Open TaskMate in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tempus2016&repository=taskmate&category=integration)
&nbsp;
[![Add TaskMate integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=taskmate)
 
> Already installed TaskMate as a custom repository from before it was accepted into HACS? It keeps working and keeps receiving updates — you can safely remove the custom repository entry, HACS now tracks it by default.
 
### Manual
 
1. Download the [latest release](https://github.com/tempus2016/taskmate/releases/latest)
2. Copy the `taskmate` folder to `/config/custom_components/taskmate/`
3. **Restart Home Assistant**
 
### Requirements

- **Home Assistant** 2024.1 or newer
- A modern browser for the dashboard cards: current Chrome, Firefox, Edge, or Safari. The cards use Web Components, Web Audio, and ES2020 features and will not work in Internet Explorer or pre-2022 browsers.

### Privacy

All TaskMate data — children, chores, points, reward claims, completion history — is stored inside your Home Assistant instance via HA's native storage helpers. Nothing is sent to any external service.

---
 
## Setup
 
### Add the Integration
 
1. **Settings** → Devices & Services → **Add Integration** → search "TaskMate"
2. Choose your **points name** (Stars, Coins, Points, Bucks — whatever motivates your children) and an **icon**. Both can be changed later in the panel.
 
That's the only thing the config flow asks. There is **no "Configure" button** on the integration card — all day-to-day management lives in the TaskMate panel below. (The legacy options/configure flow was removed in v4.0.)
 
### The TaskMate Panel
 
After installing, a **TaskMate** entry appears in the Home Assistant sidebar. This is the management hub for everything — open it and you'll find:
 
- **Children** — add children, set avatars, gift points
- **Chores** — create and edit chores, reorder, bulk-add, save/apply templates
- **Rewards** — create rewards with a fixed point cost (standard, jackpot, or savings-pool)
- **Penalties** / **Bonuses** — one-tap point deductions and awards
- **Groups** — coordinate rotation chores (sticky / spread)
- **Quests** / **Challenges** — multi-step and time-boxed goals
- **Badges** — built-in catalogue plus custom achievement badges
- **Templates** — reusable chore sets
- **Notifications** — route approval alerts to parent devices and per child
- **Settings** — points name & icon, **default card design**, history retention, streak mode, weekend multiplier, difficulty multipliers, and the bonus-points system
 
The **Activity** section shows a live feed, and chore/reward approvals are handled right in the panel. It's fully translated in all supported languages and updates in real time via WebSocket.
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/adminPanel.png" alt="TaskMate admin panel" width="700">
</p>
 
See the [Admin Panel wiki page](https://github.com/tempus2016/taskmate/wiki/Admin-Panel) for details.

### Add Cards to Your Dashboard
 
Lovelace resources are registered automatically on startup — no manual setup needed.
 
1. Edit your dashboard → **Add Card**
2. Search "taskmate" or scroll to **Custom** cards
3. Select a card, set `sensor.taskmate_overview` as the entity, configure options, save
 
---
 
## Chores & Rewards
 
### Chore Fields
 
| Field | Description |
|-------|-------------|
| **Name** | Display name shown on the child card |
| **Description** | Optional subtitle (enable with `show_description` in the card editor) |
| **Points** | Stars earned on completion |
| **Time of Day** | `Morning` `Afternoon` `Evening` `Night` `Anytime` — filters which card shows this chore |
| **Scheduling Mode** | `Specific Days` — choose which days of the week the chore appears. `Recurring` — set a repeating interval. Scheduling options are configured on the next page of the setup flow. |
| **Due Days** | (Specific Days mode) Days of the week this chore appears on the child card. Leave empty for every day. |
| **Recurrence** | (Recurring mode) How often the chore can be completed — Every 2 Days, Weekly, Every 2 Weeks, Monthly, Every 3 Months, Every 6 Months. Window is rolling from last completion date (midnight-rounded). |
| **Daily Limit** | How many times per day this chore can be completed |
| **Requires Approval** | If on, completion is pending until a parent approves — points held until approved |
| **Completion Sound** | Sound played when ticked off — overrides the card default |
| **Visibility Entity** | *(Optional)* Home Assistant entity ID that controls when this chore appears on the child card. Leave empty to always show the chore. Examples: `binary_sensor.dishwasher`, `sensor.soil_moisture`, `input_boolean.guest_mode`. See [Dynamic Chore Visibility](#dynamic-chore-visibility) for details. |
| **Visibility Operator** | How to compare the entity's current state with your target value. Options: `Equals`, `Not Equal`, `≥`, `≤`, `>`, `<`. See [Dynamic Chore Visibility](#dynamic-chore-visibility) for guidance. |
| **Visibility State** | The value to compare against. For text operators (Equals, Not Equal), enter any state value like `on`, `home`, or `away`. For numeric operators, enter a number like `30` or `50.5`. |
 
### Reward Types
 
| Type | How to Set | Description |
|------|-----------|-------------|
| **Standard** | Set `Points Cost` | Fixed cost set by the parent |
| **Jackpot** | Enable "Jackpot" toggle | A shared family goal — everyone deposits into one pooled jar (jackpots are always pool-mode) and it's redeemed once the combined total reaches the cost |
 
### Reward Approval Flow
 
Claiming is a two-step process — children can't instantly redeem rewards without parental oversight:
 
1. Child taps **Claim** → pending claim created, points **not yet deducted**
2. Parent sees the claim in the **Claims** tab of the Parent Dashboard card
3. **Approve** → points deducted, reward granted
4. **Reject** → claim cancelled, no points affected
 
---
 
## Chore Scheduling
 
Chores have two scheduling modes set in **Step 1** of the add/edit chore flow.
 
### Mode A — Specific Days
 
Choose which days of the week the chore appears on the child card. Leave empty to show every day. Use `due_days_mode` on the child card to hide or dim non-scheduled days.
 
### Mode B — Recurring
 
The chore has a rolling recurrence window. Once completed, it cannot be done again until the window expires — measured in days from the date of last completion (midnight-rounded).
 
| Recurrence | Window |
|---|---|
| Every 2 days | 2 days |
| Weekly | 7 days |
| Every 2 weeks | 14 days |
| Monthly | 30 days |
| Every 3 months | 90 days |
| Every 6 months | 180 days |
 
**Optional settings for recurring chores:**
- **Day of Week** — for Weekly/Every 2 Weeks, pin the chore to a specific day
- **Start Date** — for Every 2 Days, set the anchor date for the rhythm
- **First Occurrence** — Available Immediately (default) or Wait for First Scheduled Occurrence
 
**Child card behaviour:** Use `recurrence_done_mode` on the child card to control what happens when a recurring chore has been completed and is waiting to reset — `dim` (default), `hide`, or `show`.
 
---
 
## Dynamic Chore Visibility
 
Show or hide chores based on the state of a Home Assistant entity. Chores only appear on the child card when the visibility condition is met.
 
### How It Works
 
When you create or edit a chore, set the **Visibility Entity** (e.g., `binary_sensor.dishwasher`), **Visibility Operator** (e.g., `Equals`), and **Visibility State** (e.g., `running`). The chore appears on the child card only when the entity's current state matches your condition.
 
**Examples:**
- **Dishwasher chores** — Set entity to `binary_sensor.dishwasher` with operator `Equals` and state `on`. Chores only appear when the dishwasher is running.
- **Soil moisture** — Set entity to `sensor.soil_moisture` with operator `≤` and state `30`. Chores only appear when moisture is 30% or lower.
- **Guest mode** — Set entity to `input_boolean.guest_mode` with operator `Not Equal` and state `on`. Chores only appear when guests are not over.
- **Temperature threshold** — Set entity to `sensor.temperature` with operator `>=` and state `25`. Chores only appear when it's warm enough.
 
### Visibility Operators
 
| Operator | Use When | Example |
|----------|----------|---------|
| **Equals** | Entity state matches exactly (case-insensitive) | Entity: `binary_sensor.dishwasher`, State: `on` — show when entity is "on" |
| **Not Equal** | Entity state does not match | Entity: `input_boolean.guest_mode`, State: `on` — show when guests are NOT over |
| **≥** (Greater or Equal) | Numeric entity value is at or above threshold | Entity: `sensor.battery_percent`, State: `80` — show when battery ≥ 80% |
| **≤** (Less or Equal) | Numeric entity value is at or below threshold | Entity: `sensor.soil_moisture`, State: `30` — show when moisture ≤ 30% |
| **>** (Greater Than) | Numeric entity value is above threshold | Entity: `sensor.temperature`, State: `25` — show when temperature > 25°C |
| **<** (Less Than) | Numeric entity value is below threshold | Entity: `sensor.snow_depth`, State: `10` — show when snow < 10 cm |
 
### Key Points
 
- **Optional** — Leave Visibility Entity empty to always show the chore
- **Entity types** — Works with any entity: `binary_sensor`, `sensor`, `input_boolean`, `switch`, `number`, etc.
- **Update frequency** — Visibility is checked every 30 seconds (coordinator refresh interval)
- **Safe fallback** — If the entity becomes unavailable, the chore defaults to **visible**
- **Frontend only** — Visibility only hides chores from the child card. Parent services like `taskmate.complete_chore` will still work on hidden chores
- **Numeric handling** — Numeric operators automatically convert entity state to a number. If conversion fails, the operators fall back to string matching.
 
### Common Use Cases
 
**Chores that only appear when equipment is in use:**
- Dishwasher loading chores when `binary_sensor.dishwasher` is `on`
- Laundry folding when `binary_sensor.dryer` is `on`
 
**Seasonal or conditional chores:**
- Snow shovelling when `sensor.snow_depth` > 5 cm
- Watering plants when `sensor.soil_moisture` ≤ 40%
- Yard work when `binary_sensor.guest_mode` is `off`
 
**Time-based or system state:**
- Tasks only when home alone (entity not set to `away`)
- Tasks only during school days (custom `input_boolean.school_day`)
- Tasks only when a family member is home (entity is `home`)
 
---
 
## Bonus Points System
 
All bonus settings live in the **Settings** tab of the TaskMate panel (sidebar → TaskMate → Settings).

<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/adminSettings.png" alt="TaskMate panel settings" width="700">
</p>
 
### Weekend Points Multiplier
 
Children earn extra points for completing chores on Saturdays and Sundays.
 
- Default multiplier: **2.0×** — a 10-point chore on Saturday earns 20 points
- The multiplier applies to the **completion date**, not the approval date
- Configure: `1.0` to `5.0` (set `1.0` to disable)
 
### Streak Milestone Bonuses
 
Bonus points are awarded when a child hits a streak milestone. Fully configurable — enter your own milestones as `days:points` pairs:
 
```
3:5, 7:10, 14:20, 30:50, 60:100, 100:200
```
 
| Default Streak | Default Bonus |
|----------------|---------------|
| 3 days  | +5 pts |
| 7 days  | +10 pts |
| 14 days | +20 pts |
| 30 days | +50 pts |
| 60 days | +100 pts |
| 100 days | +200 pts |
 
- Milestones are **re-earnable** after a streak resets
- Use the **Streak Milestone Bonuses** toggle as a master on/off switch
- Leave the configuration field empty to disable all milestones without turning off the toggle
- Invalid formats fall back to the default list with a validation error shown on save
 
### Perfect Week Bonus
 
Children earn a bonus when they complete at least one chore every day Monday–Sunday.
 
- Checked automatically every **Monday at midnight**
- Default: **50 points** — configurable from 10 to 500
 
### Settings Reference
 
| Setting | Default | Description |
|---------|---------|-------------|
| Weekend Points Multiplier | `2.0` | Multiplier on Sat/Sun (1.0 = off) |
| Streak Milestone Bonuses | `on` | Master toggle |
| Streak Milestone Configuration | `3:5, 7:10, 14:20, 30:50, 60:100, 100:200` | Custom `days:points` pairs |
| Perfect Week Bonus | `on` | Toggle |
| Perfect Week Bonus Points | `50` | Points per perfect week |
| Streak Reset Mode | `reset` | `reset` — streak drops to 0 on a missed day; `pause` — streak is preserved |
| History Days to Keep | `90` | Completion history retention, 30–365 days |
 
---
 
## Notifications
 
TaskMate can notify parents when a chore requiring approval has been completed.
 
### How It Works
 
When a child completes a chore that has **Requires Approval** turned on:
 
1. A **persistent notification** is always created in HA — visible in the notification bell in the sidebar
2. If a **notification target** is configured in the panel's Notifications tab, a push notification is also sent
 
### Configuring Push Notifications
 
Open the **Notifications** tab of the TaskMate panel (sidebar → TaskMate → Notifications). There you can:
 
- Add one or more **parent notification targets**, each pointing at a notify service such as `notify.mobile_app_your_phone`, with an individual enable toggle
- Route notifications **per child** to a specific notify service
- Send a **test notification** to confirm a target works
 
Leave all targets empty to use persistent (in-app) notifications only.

> **Note:** Targets must be in the `notify` domain (e.g. `notify.mobile_app_...`). Services from other domains are ignored with a warning in the HA logs.

> **Tip:** Use `binary_sensor.taskmate_has_pending_approvals` in your own automations for more customised notification logic.
 
---
 
## Penalties

Deduct points from a child for unwanted behaviour — the flip side of the reward system.

### How It Works

1. Create named penalties (e.g. "Not going to bed = 10 points") via the **Penalties Card** or the `taskmate.add_penalty` service
2. Open the Penalties Card, select the child, and tap **Apply** on the relevant penalty
3. Points are deducted immediately and logged in the activity feed as `Penalty: <name>`

- Select the child using the tabs at the top (hidden if only one child)
- Tap **Apply** to deduct points instantly — the tile flashes and a toast confirms the action
- Tap the **pencil icon** to enter edit mode: add new penalties, edit name/points/icon/description, or delete

### Managing Penalties via Services

```yaml
# Create a penalty
service: taskmate.add_penalty
data:
  name: "Not going to bed"
  points: 10
  description: "Refused bedtime after two warnings"   # optional
  icon: mdi:bed-clock                                 # optional, any MDI icon

# Apply a penalty to a child
service: taskmate.apply_penalty
data:
  penalty_id: abc12345    # see Finding IDs
  child_id: a8c8376a
```

---

## Achievement Badges

Milestone-based recognition layered on top of the existing chores / streak / reward systems. 15 built-in badges across four tiers (Bronze / Silver / Gold / Platinum), plus full support for parent-created custom badges with multi-criterion AND rules.

### Built-in Catalogue

| Tier | Examples |
|---|---|
| Bronze | First Chore, First Reward, 100 Points, 10 Chores Completed |
| Silver | 500 Points, 50 Chores, 3-Day Streak, First Perfect Week |
| Gold | 1000 Points, 100 Chores, 7-Day Streak, 5 Perfect Weeks |
| Platinum | 5000 Points, 30-Day Streak, 10 Perfect Weeks |

Built-ins can be enabled / disabled and have their `point_bonus`, tier, assignment, and notify-on-earn edited. Their criteria, name, description, and icon are frozen so installs stay consistent.

### Custom Badges

Define your own with any combination of metric thresholds (AND-evaluated):

- `total_points` ≥ N
- `total_chores` ≥ N
- `total_rewards` ≥ N
- `current_streak` ≥ N
- `best_streak` ≥ N
- `perfect_weeks` ≥ N
- `first_chore` (1 = earned on first completion)
- `first_reward` (1 = earned on first reward claim)

Empty criteria = manual-award only (parent presses "Award to..." to grant it).

### Display

- **`taskmate-badges-card`** — full grid view per child. Earned tiles in tier colour, locked tiles greyed with progress bars showing closest-criterion completion percentage.
- **`taskmate-child-card`** — inline strip of up to 5 most-recently-earned badges below the points readout (auto-hidden when zero earned). Tap → opens the admin panel's badges section. Disable with `show_badges: false`.
- **Admin panel — Badges section** — Catalogue / Custom / Award History tabs. Award History shows AUTO / MANUAL / SILENT source pills and supports one-click revoke (auto-reverses any point bonus credited).

### Sensor

Each child gets `sensor.taskmate_badges_<slug>`:
- State: count of earned badges
- Attributes: `earned[]` (with `earned_at`, `tier`, etc.), `available[]` (with `progress_pct`), `total_badges`

### Retroactive Backfill

On first install of v3.8.0, existing kids get badges silently retroactive-awarded for milestones they've already passed (e.g. a kid with 200 points instantly has the "100 Points" badge). Silent backfill never fires notifications and never credits `point_bonus` — the feature works on day one without point inflation.

The `taskmate.rebuild_badges` service re-runs this sweep on demand (e.g. after enabling a previously-disabled built-in).

### Notifications

Persistent HA notification + optional mobile push when a badge auto-earns. Per-badge `notify_on_earn` toggle (default true). When 3+ badges earn in a single evaluation, notifications batch into a single combined message.

### Services

```yaml
# Add a custom badge
service: taskmate.add_badge
data:
  name: "Holiday Helper"
  description: "Earned for big effort during school holidays"
  icon: mdi:beach
  tier: silver
  point_bonus: 30
  criteria:
    - { metric: total_chores, operator: ">=", value: 20 }
    - { metric: current_streak, operator: ">=", value: 3 }
  assigned_to: [c1, c2]            # empty = all kids
  notify_on_earn: true

# Manually award a badge
service: taskmate.award_badge_manually
data:
  badge_id: abc12345
  child_id: a8c8376a

# Revoke an awarded badge (reverses any point_bonus that was credited)
service: taskmate.revoke_badge
data:
  awarded_badge_id: xyz98765       # see the panel's Award History tab

# Re-evaluate all badges across all children silently
service: taskmate.rebuild_badges
```

Other services: `taskmate.update_badge`, `taskmate.remove_badge` (custom only — built-ins protected).

---

## Timed Tasks

Duration-based chores where children earn points based on how long they spend on an activity — ideal for reading, practising instruments, or homework.

1. Set a chore's **Task Type** to `timed` in the admin panel
2. Configure the rate (e.g. 10 points per 5 minutes) and optional daily cap
3. The child starts, pauses, and stops a timer on their card
4. Points are calculated as `floor(total_seconds / (rate_minutes × 60)) × rate_points`

Services: `taskmate.start_timed_task`, `taskmate.pause_timed_task`, `taskmate.stop_timed_task`

See the [Timed Tasks wiki page](https://github.com/tempus2016/taskmate/wiki/Timed-Tasks) for full details.

---

## Task Groups

Coordinate related rotation-mode chores so they're assigned to the same child (sticky) or spread across different children (spread). For example, a "Dinner Duties" group ensures that the child who sets the table also clears it.

- **Sticky** — all chores in the group follow the leader chore's assignment
- **Spread** — chores in the group are assigned to different children

Manage groups via the admin panel or the `taskmate.add_task_group` / `taskmate.update_task_group` / `taskmate.remove_task_group` services.

See the [Task Groups wiki page](https://github.com/tempus2016/taskmate/wiki/Task-Groups) for full details.

---

## Quests

A **Quest** is an ordered chain of chores a child works through step by step. They complete each chore in sequence, and when the **final step** is done (and approved, if that chore requires approval), they earn a one-time **bonus** on top of the points from the chores themselves. Think of it as a themed multi-step mission — "Morning Routine", "Saturday Tidy-Up", "Get Ready for School".

Create and manage quests in the **Quests** tab of the TaskMate panel (you need at least one chore first):

| Field | Default | Description |
|---|---|---|
| **Name** / **Description** / **Icon** | `mdi:map-marker-path` | Display details |
| **Steps** | — | The ordered list of chores that make up the quest (pick from your existing chores) |
| **Bonus points** | `25` | One-time reward granted when the last step is completed |
| **Assigned to** | all children | Which children can take the quest — leave empty for everyone |
| **Repeatable** | off | When on, progress resets after completion so the child can run it again; when off, it stays done once finished |
| **Active** | on | Turn off to hide a quest without deleting it |

**Key points:**
- Progress is **per child** — each child works through the chain independently, and the panel shows each child's current step.
- Steps advance only when the current step's chore is completed (and approved, if required) — they must be done in order.
- A repeatable quest tracks how many times each child has completed it.
- If a chore used as a step is later deleted, the step shows as a missing chore; the rest of the quest is unaffected.
- Completing a quest fires a `taskmate_quest_completed` event (with `child_id`, `quest_id`, `bonus`, …) you can use in your own automations.

---

## Challenges

A **Challenge** is a time-boxed target that refreshes every period. Within each **daily** or **weekly** window, a child works toward a goal — complete *N* chores, or earn *N* points — and the moment they hit it they get a one-time **bonus**. Progress and the reward reset automatically when the period rolls over, so a daily challenge is a fresh goal every day. Unlike a Quest (a fixed chore chain), a Challenge just measures output over a window.

Create and manage challenges in the **Challenges** tab of the TaskMate panel:

| Field | Default | Description |
|---|---|---|
| **Name** / **Description** / **Icon** | `mdi:trophy-outline` | Display details |
| **Scope** | `daily` | The reset window — `daily` (resets at midnight) or `weekly` (resets Monday) |
| **Metric** | `chores` | What counts toward the target — `chores` completed or `points` earned |
| **Target** | `3` | The value the child must reach within the period |
| **Bonus points** | `15` | Reward granted once per period when the target is met |
| **Assigned to** | all children | Which children the challenge applies to — leave empty for everyone |
| **Active** | on | Turn off to pause a challenge without deleting it |

**Key points:**
- Only **approved** chore completions count toward progress; bonus subtasks are excluded.
- The bonus is awarded **once per period** — hitting the target again in the same day/week doesn't pay out twice.
- Progress is tracked **per child** against the same shared target — it's not a head-to-head race between siblings.
- Daily challenges reset at midnight; weekly challenges reset on Monday (ISO week). A target met just before the boundary does not carry into the next period.
- Completing a challenge fires a `taskmate_challenge_completed` event (with `child_id`, `challenge_id`, `scope`, `bonus`, …) for use in automations.

---

## Pool Mode (Savings Jars)

Children can save up for expensive rewards over time by depositing points into a dedicated savings pool. Points are locked once deposited — there is no withdrawal.

- Enable pool mode per reward in the admin panel
- Children deposit points via the Rewards Card or `taskmate.allocate_points_to_pool`
- Once the pool reaches the reward cost, the child can claim it

See the [Pool Mode wiki page](https://github.com/tempus2016/taskmate/wiki/Pool-Mode-(Savings-Jars)) for full details.

---

## Dashboard Cards
 
> **Header colours:** Every card has a configurable `header_color` option in the visual editor, with its own vibrant default. Change it to match your dashboard theme or differentiate kid vs parent cards.
 
> **Design styles (v4.2.0+):** Every card also has a `card_design` option — choose **Classic** (the original look), **Playroom** (warm, rounded, picture-book), **Console** (dark, neon game-HUD), or **Clean Pro** (minimal, flat). Set it per card in the visual editor or in YAML (`card_design: playroom`), or leave it on **Global default** (`card_design: global`) to follow the integration-wide style set in the panel's **Settings → Default card design**. Styles are scoped per card, so you can mix and match across a dashboard.
 
### Card Overview
 
| Card | Best For | Purpose |
|------|----------|---------|
| [Child Card](#child-card) | Kids | Complete chores — big buttons, sounds, celebrations |
| [Rewards Card](#rewards-card) | Kids | View rewards, track progress, claim |
| [Approvals Card](#approvals-card) | Parents | Approve/reject pending chore completions |
| [Points Card](#points-card) | Parents | Manually add or remove points |
| [Reorder Card](#reorder-card) | Parents | Drag-and-drop chore display order |
| [Parent Dashboard Card](#parent-dashboard-card) | Parents | All-in-one: approvals, claims, overview, points |
| [Overview Card](#overview-card) | Parents | At-a-glance all-children progress |
| [Activity Card](#activity-card) | Parents | Full activity timeline |
| [Streak Card](#streak-card) | Both | Streak history and achievement badges |
| [Weekly Card](#weekly-card) | Parents | Mon–Sun bar chart and stats |
| [Points Graph Card](#points-graph-card) | Parents | Points over time, multi-child line graph |
| [Reward Progress Card](#reward-progress-card) | Kids | Full-screen motivational reward display |
| [Leaderboard Card](#leaderboard-card) | Both | Competitive ranking by points, streak, or weekly |
| [Penalties Card](#penalties-card) | Parents | Apply point-deduction penalties |
| [Bonuses Card](#bonuses-card) | Parents | Apply one-tap point bonuses |
| [Points Display Card](#points-display-card) | Kids | Big, kid-friendly points readout |
| [Calendar Card](#calendar-card) | Both | One-day view of chores assigned to each child |
 
---
 
### Child Card
 
Kid-friendly chore completion. The entire row is tappable — no small targets. Supports colourful animated badges, confetti celebrations, and completion sounds. Tapping a completed chore undoes it.
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/childCard.png" alt="Child Card" width="300">
</p>
 
```yaml
type: custom:taskmate-child-card
entity: sensor.taskmate_overview
child_id: a8c8376a            # required — see Finding IDs
time_category: anytime        # any period id (built-in or custom) | anytime | all
due_days_mode: hide           # hide | dim | show — chores not scheduled today
recurrence_done_mode: dim     # dim | hide | show — recurring chores waiting to reset
elapsed_time_mode: dim        # dim | hide | show — time-of-day chores whose period has passed
show_countdown: true          # show midnight reset countdown
show_description: false       # show chore description below name
default_sound: coin           # default completion sound
undo_sound: undo              # sound when undoing
header_color: "#9b59b6"
```

**`elapsed_time_mode`** — controls what happens to time-of-day chores once that time window has passed without completion. Set to `dim` (default) to grey them out and make them non-interactive, `hide` to remove them entirely, or `show` to leave them active. Chores set to `Anytime` are never affected. Chores that were completed still show with their green done style regardless.

Time-of-day periods are fully customisable in **Settings → Time-of-day boundaries** in the TaskMate admin panel: rename the built-in four, change their hours and icons, or add as many of your own (school run, bedtime, …) as you like. Periods can't overlap; gaps between them fall back to Anytime, and a period that still has chores assigned can't be deleted until they're reassigned. A chore's or card's `time_category` accepts any period id.
 
---
 
### Rewards Card
 
Shows all available rewards with progress bars and claim buttons. After claiming, the button shows "Awaiting parent approval" until approved. If you don't set `child_id`, the card shows a **child picker** at the top so you can choose who is claiming (for households with more than one child). Jackpot rewards show pooled **deposit** controls and a colour-coded contribution bar per child instead of a single claim button.
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/rewardCard.png" alt="Rewards Card" width="500">
</p>
 
```yaml
type: custom:taskmate-rewards-card
entity: sensor.taskmate_overview
child_id: a8c8376a            # optional — pin to one child; omit to show a child picker
show_child_badges: true       # show which children are assigned each reward
deposit_amounts: [10, 50, 100] # optional — quick-deposit button amounts for pool/jackpot rewards (default [1, 5, 10])
header_color: "#e67e22"
```

> **Pool deposits:** Jackpot and savings-pool rewards show quick-deposit buttons plus an **Amount** field where a child can type any custom amount — handy for large goals. Set `deposit_amounts` to change the quick buttons (e.g. `[10, 50, 100]`); the custom field always accepts any value and is capped to the child's spendable balance and the pool's remaining room.
 
---
 
### Approvals Card
 
Review and approve or reject chore completions requiring parent sign-off. Items are grouped by date and time of day.
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/pendingApproval.png" alt="Pending Approvals" width="500">
</p>
 
```yaml
type: custom:taskmate-approvals-card
entity: sensor.taskmate_overview
title: Pending Approvals      # optional
child_id: a8c8376a            # optional — filter to one child
header_color: "#27ae60"
```
 
---
 
### Points Card
 
Manually award bonus points or deduct points for consequences — useful for situations outside the normal chore flow.
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/managePoints.png" alt="Manage Points" width="500">
</p>
 
Each child row shows two rows of quick-tap buttons — one for adding, one for removing. Tap a button to apply instantly with no dialog. The `⋯` button opens a dialog for a custom amount with an optional reason.
 
```yaml
type: custom:taskmate-points-card
entity: sensor.taskmate_overview
title: Manage Points
quick_add_amounts: [1, 5, 10]      # configurable add buttons
quick_remove_amounts: [1, 5, 10]   # configurable remove buttons
show_dialog: true                  # show ⋯ for custom amount + reason
header_color: "#2980b9"
```
 
---
 
### Reorder Card
 
Drag-and-drop interface to set the order chores appear for each child.
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/reorderCard.png" alt="Reorder Card" width="500">
</p> Saves per-child.
 
```yaml
type: custom:taskmate-reorder-card
entity: sensor.taskmate_overview
child_id: a8c8376a
title: Reorder Chores
header_color: "#16a085"
```
 
---
 
### Parent Dashboard Card
 
The most useful parent card — four tabs in one:
 
- **Overview** — all children's progress and points
- **Approvals** — pending chore completions with inline approve/reject
- **Claims** — pending reward claims with approve/reject
- **Points** — quick +/- buttons per child
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/parent-dashboard.png" alt="Parent Dashboard" width="500">
</p>
 
```yaml
type: custom:taskmate-parent-dashboard-card
entity: sensor.taskmate_overview
title: Parent Dashboard
quick_points_amount: 5        # points per +/- button press
show_claims: true             # show the Claims tab
header_color: "#c0392b"
```
 
---
 
### Overview Card
 
At-a-glance view of every child — today's chore progress bars, current points, and a pulsing red badge when approvals are pending. Progress counts only chores due today — chores with `due_days` set are excluded from the total on days they are not scheduled.
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/overview.png" alt="Overview" width="500">
</p>
 
```yaml
type: custom:taskmate-overview-card
entity: sensor.taskmate_overview
title: TaskMate
header_color: "#8e44ad"
```
 
---
 
### Activity Card
 
Scrollable timeline of everything — chore completions, manual point adjustments, bonus point events (weekends, streaks, perfect weeks), and reward claims. Grouped by Today / Yesterday / date.
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/activity.png" alt="Activity" width="500">
</p>
 
```yaml
type: custom:taskmate-activity-card
entity: sensor.taskmate_overview
child_id: a8c8376a            # optional — filter to one child
max_items: 30
header_color: "#2471a3"
```
 
---
 
### Streak Card
 
Per-child streak display with a dot history grid, current and best streak, and achievement badges.
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/streak.png" alt="Streak" width="500">
</p>
 
```yaml
type: custom:taskmate-streak-card
entity: sensor.taskmate_overview
child_id: a8c8376a            # optional — filter to one child
streak_days_shown: 14         # days shown in the dot history grid
header_color: "#e74c3c"
```
 
---
 
### Weekly Card
 
Monday–Sunday bar chart
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/weeklyCard.png" alt="Weekly Card" width="500">
</p> with headline stats (chores completed, points earned, days active). Counts only approved completions.
 
```yaml
type: custom:taskmate-weekly-card
entity: sensor.taskmate_overview
child_id: a8c8376a            # optional — filter to one child
header_color: "#27ae60"
```
 
---
 
### Points Graph Card
 
Canvas-based line graph
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/pointsGraph.png" alt="Points Graph" width="500">
</p> of points over time. Supports multiple children with colour-coded lines and a hover/touch tooltip.
 
```yaml
type: custom:taskmate-graph-card
entity: sensor.taskmate_overview
child_id: a8c8376a            # optional — filter to one child
days: 14                      # date range: 3–90
header_color: "#d35400"
```
 
---
 
### Reward Progress Card
 
Full-screen motivational display
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/rewardProgressCard.png" alt="Reward Progress" width="500">
</p> for a single reward — animated progress bar, floating reward icon, and a pulsing "Ready to claim!" badge. Designed for wall-mounted tablets.
 
```yaml
type: custom:taskmate-reward-progress-card
entity: sensor.taskmate_overview
reward_id: abc123             # required — see Finding IDs
child_id: a8c8376a            # optional — show one child's contribution
title: Reward Goal
header_color: "#7d3c98"
```
 
---
 
### Leaderboard Card
 
Competitive ranking
 
<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/leaderboardCard.png" alt="Leaderboard" width="500">
</p> of all children. Top 3 get gold/silver/bronze styling. For single-child households, automatically shows a personal bests display instead.
 
```yaml
type: custom:taskmate-leaderboard-card
entity: sensor.taskmate_overview
sort_by: points               # points | streak | weekly
show_streak: true
show_weekly: true
header_color: "#b7950b"
```

---

### Penalties Card

Parent-facing card for applying point-deduction penalties. Select the child using tabs, then tap **Apply** next to the relevant penalty. Tap the pencil icon to add, edit, or delete penalty definitions.

<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/penalties.png" alt="Penalties Card" width="500">
</p>

```yaml
type: custom:taskmate-penalties-card
entity: sensor.taskmate_overview
title: Penalties
header_color: "#e74c3c"
```

---

### Bonuses Card

Parent-facing counterpart to the Penalties Card. Define one-tap point bonuses and apply them to any child from the card. Use the pencil icon to add, edit, or delete bonus definitions.

```yaml
type: custom:taskmate-bonuses-card
entity: sensor.taskmate_overview
title: Bonuses
header_color: "#27ae60"
```

**Managing Bonuses via Services:**

```yaml
# Create a bonus
service: taskmate.add_bonus
data:
  name: "Helped a sibling"
  points: 15
  description: "Voluntary help without being asked"   # optional
  icon: mdi:hand-heart                                # optional

# Apply a bonus to a child
service: taskmate.apply_bonus
data:
  bonus_id: abc12345    # see Finding IDs
  child_id: a8c8376a
```

---

### Points Display Card

Big, kid-friendly readout of current points. Supports three modes: a single child, every child side-by-side, or the combined family total. Pair it with the Child Card on a tablet dashboard.

```yaml
type: custom:taskmate-points-display-card
entity: sensor.taskmate_overview
mode: single            # single | multi | cumulative (default: single)
child_id: a8c8376a      # required when mode: single
header_color: "#2980b9"
card_design: global     # global | classic | playroom | console | cleanpro
```

---

### Calendar Card

One-day view of the chores assigned to each child. Each child gets a section showing the chores scheduled for the selected day, colour-coded by state: **green** = approved, **amber** = pending approval, **grey** = due but not completed. Rotating-assignment chores (alternating, random, balanced) render dimmed on days other than today so you can see they rotate.

Use the ◀ / ▶ buttons to step through days, or the calendar icon to jump back to today. Set `child_id` to show only a single child.

```yaml
type: custom:taskmate-calendar-card
entity: sensor.taskmate_overview
title: Task Calendar
child_id: a8c8376a            # optional — show only one child
header_color: "#3498db"
```

---

## Services
 
TaskMate exposes services you can call from automations, scripts, or Developer Tools.

> **v3.7.0+:** All entity ID fields (`child_id`, `chore_id`, `reward_id`, etc.) now show as **dropdown selectors** in the HA automation editor with entity names as labels. You can still type raw hex IDs if you prefer.

### Chore Services

| Service | Parameters | Description |
|---------|-----------|-------------|
| `taskmate.complete_chore` | `chore_id`, `child_id` | Mark a chore as completed |
| `taskmate.approve_chore` | `completion_id` | Approve a pending chore completion |
| `taskmate.reject_chore` | `completion_id` | Reject a pending chore completion |
| `taskmate.add_chore` | `name`, `points`\*, `assigned_to`\*, `time_category`\*, `one_shot`\*, `requires_approval`\* | Create a chore dynamically |
| `taskmate.skip_chore` | `chore_id` | Skip today's assigned child in a rotation chore |
| `taskmate.set_chore_manual_start` | `chore_id`, `child_id` | Override which child starts the rotation |
| `taskmate.complete_bonus_subtask` | `chore_id`, `bonus_subtask_id`, `child_id` | Complete a bonus subtask within a chore |

### Timed Task Services

| Service | Parameters | Description |
|---------|-----------|-------------|
| `taskmate.start_timed_task` | `chore_id`, `child_id` | Start or resume a timed task timer |
| `taskmate.pause_timed_task` | `chore_id`, `child_id` | Pause a running timed task |
| `taskmate.stop_timed_task` | `chore_id`, `child_id` | Stop timer and submit for approval |

### Reward Services

| Service | Parameters | Description |
|---------|-----------|-------------|
| `taskmate.claim_reward` | `reward_id`, `child_id` | Create a pending reward claim |
| `taskmate.approve_reward` | `claim_id` | Approve a reward claim (deducts points) |
| `taskmate.reject_reward` | `claim_id` | Reject a reward claim |
| `taskmate.allocate_points_to_pool` | `child_id`, `reward_id`, `points` | Deposit points into a reward's savings pool |

### Points Services

| Service | Parameters | Description |
|---------|-----------|-------------|
| `taskmate.add_points` | `child_id`, `points`, `reason`\* | Manually add points to a child |
| `taskmate.remove_points` | `child_id`, `points`, `reason`\* | Manually remove points from a child |

### Penalty Services

| Service | Parameters | Description |
|---------|-----------|-------------|
| `taskmate.add_penalty` | `name`, `points`, `description`\*, `icon`\*, `assigned_to`\* | Create a new penalty definition |
| `taskmate.update_penalty` | `penalty_id`, `name`\*, `points`\*, `description`\*, `icon`\*, `assigned_to`\* | Update an existing penalty |
| `taskmate.remove_penalty` | `penalty_id` | Delete a penalty definition |
| `taskmate.apply_penalty` | `penalty_id`, `child_id` | Apply a penalty — deducts points immediately |

### Bonus Services

| Service | Parameters | Description |
|---------|-----------|-------------|
| `taskmate.add_bonus` | `name`, `points`, `description`\*, `icon`\*, `assigned_to`\* | Create a new bonus definition |
| `taskmate.update_bonus` | `bonus_id`, `name`\*, `points`\*, `description`\*, `icon`\*, `assigned_to`\* | Update an existing bonus |
| `taskmate.remove_bonus` | `bonus_id` | Delete a bonus definition |
| `taskmate.apply_bonus` | `bonus_id`, `child_id` | Apply a bonus — awards points immediately |

### Task Group Services

| Service | Parameters | Description |
|---------|-----------|-------------|
| `taskmate.add_task_group` | `name`, `policy`, `chore_ids`\* | Create a task group (sticky or spread) |
| `taskmate.update_task_group` | `group_id`, `name`\*, `policy`\*, `chore_ids`\* | Update a task group |
| `taskmate.remove_task_group` | `group_id` | Delete a task group |

### Other Services

| Service | Parameters | Description |
|---------|-----------|-------------|
| `taskmate.set_chore_order` | `child_id`, `chore_order` | Set the chore display order for a child |
| `taskmate.preview_sound` | `sound` | Preview a completion sound in the browser |

\* optional

See the [Services wiki page](https://github.com/tempus2016/taskmate/wiki/Services) for full parameter details, examples, and side effects.

**Example — award bonus points from an automation:**
 
```yaml
service: taskmate.add_points
data:
  child_id: a8c8376a
  points: 10
  reason: "Helped with the shopping"
```
 
---
 
## Jackpot Rewards
 
Enable **Jackpot** mode on a reward for big family goals — a holiday, a theme-park trip, a board game everyone wants. Jackpots are **always pooled**: each assigned child **deposits** points into the shared jar (deposited points are locked in), and once the combined total reaches the cost the reward can be **redeemed** — so a goal no single child could afford on their own is reached together. The rewards card shows each child's contribution as a colour-coded bar segment.
 
Because jackpots are inherently pooled, the reward editor manages pool mode for them automatically — there's no separate Pool toggle to set. See [Pool Mode (Savings Jars)](#pool-mode-savings-jars) for how depositing and redeeming work.
 
---
 
## Completion Sounds
 
The child card plays a sound when a chore is ticked off. All synthesised sounds are generated via the Web Audio API — no external files needed.
 
| Sound | Type | Description |
|-------|------|-------------|
| `coin` | Synth | Classic video game coin collect |
| `levelup` | Synth | Triumphant ascending arpeggio |
| `fanfare` | Synth | Celebratory trumpet fanfare |
| `chime` | Synth | Pleasant bell chime |
| `powerup` | Synth | Ascending sweep with sparkle |
| `undo` | Synth | Sad descending womp-womp (played on undo) |
| `fart1`–`fart10` | Audio file | Real fart sounds (CC0 — BigSoundBank.com) |
| `fart_random` | Audio file | Random fart sound 1–10 |
| `none` | — | Silence |
 
**Fart sounds** require the audio files placed at `/config/www/taskmate/fart1.mp3` through `fart10.mp3`.
 
Priority order: **chore-level sound** → **card `default_sound`** → `coin`
 
---
 
## Finding IDs
 
Several card options and service calls require a `child_id`, `chore_id`, `reward_id`, etc.

### Method 1 — Show IDs Toggle (easiest)

Open the **TaskMate Admin Panel** (sidebar) → **Settings** tab → flip **Show IDs**. Every entity card/row across all tabs displays its hex ID in a monospace badge with a click-to-copy button.

### Method 2 — Automation Editor Dropdowns

Since v3.7.0, all entity ID fields in the HA automation editor and Developer Tools → Services show as **dropdown selectors** with entity names. You can pick "Noah" instead of typing `ef19c56175c14bd9` — no need to look up the ID at all.

### Method 3 — Sensor Attributes

1. Go to **Developer Tools** → **States**
2. Find `sensor.taskmate_overview` → `children` array for child IDs
3. Find `sensor.taskmate_chores` → `chores` array for chore IDs
4. Find `sensor.taskmate_rewards` → `rewards` array for reward IDs
5. Find `sensor.taskmate_incentives` → `penalties` / `bonuses` arrays for penalty/bonus IDs

## Sensors Exposed

Home Assistant limits a single entity's attribute payload to 16 KB for the
recorder. TaskMate therefore splits its data across several global sensors
and per-child sensors. Cards configured with `entity: sensor.taskmate_overview`
keep working unchanged — every TaskMate card internally merges attributes from
the overview sensor and its companion sensors at render time.

| Entity | State | What lives here |
|---|---|---|
| `sensor.taskmate_overview` | total children | `children` summary, `points_name`, `points_icon`, `today_day_of_week`, totals, streak / perfect-week settings |
| `sensor.taskmate_chores` | total chores | `chores` list (definitions), `todays_completions` |
| `sensor.taskmate_chore_availability` | total chores available today | `chore_availability`: `{chore_id: {child_id: bool}}` |
| `sensor.taskmate_rewards` | total rewards | `rewards`, `pending_reward_claims`, `pool_allocations` |
| `sensor.taskmate_activity` | total completions all-time | `recent_completions` (last 35), `recent_transactions` (last 20) |
| `sensor.taskmate_incentives` | penalties + bonuses count | `penalties`, `bonuses` |
| `sensor.taskmate_pending_approvals` | pending approvals count | `chore_completions`, `reward_claims` (detailed lists) |
| `sensor.taskmate_<child>_points` | points for that child | `child_id`, `current_streak`, `best_streak`, `total_*` |
| `sensor.taskmate_<child>_stats` | chores completed by that child | `assigned_chores`, streak / totals |

Automations that read the old overview attributes (e.g. `sensor.taskmate_overview.attributes.chores`) should instead read from the matching companion sensor listed above.
 
---
 
## Troubleshooting
 
**Cards show "Custom element doesn't exist"**
- Hard refresh the browser (Cmd+Shift+R / Ctrl+Shift+R)
- Check Settings → Dashboards → Resources — the `/taskmate/*.js` resources should be listed
- If resources are missing, restart Home Assistant — they are registered automatically on startup
 
**Cards show "Entity not found"**
- Make sure you're using `sensor.taskmate_overview` as the entity (not `sensor.taskmate_pending_approvals`)
- Verify the TaskMate integration is loaded: Settings → Devices & Services → TaskMate
 
**Chore description not showing**
- Enable **Show chore description** in the child card editor
- Make sure the chore actually has a description set in Settings → Manage Chores
 
**Points not updating after completing a chore**
- If the chore requires approval, points are held in "pending" until a parent approves
- The pending points are shown separately in the child card header
 
**Streak not incrementing**
- Streaks update at midnight. If you complete chores late at night and check before midnight, the streak counter won't have updated yet
- If Streak Reset Mode is set to `reset`, missing a single day resets the streak to 0
 
**Resources keep disappearing after restart**
- Restart Home Assistant — Lovelace resources are registered automatically on startup
- If the problem persists after restarting, check the HA logs for errors from the `taskmate` integration
 
---
 
## Tips
 
- **Two dashboards** — One for children (Child Card + Rewards Card), one for parents (Parent Dashboard). Children don't need to see the approval queue
- **Completion %** — Set this lower for optional or weekly chores. If a chore is done twice a week, set it to ~30%. This prevents infrequent chores from inflating reward costs
- **Due Days** — Use these so Monday's homework doesn't appear on Saturday. Set `due_days_mode: hide` on the child card
- **Chore descriptions** — Add short instructions like "Put the lid back on the bin" and enable `show_description: true` in the card editor
- **Streak mode: Pause** — If you go on holiday, "Pause" mode means children don't lose their streak. "Reset" mode is stricter and more motivating for consistent households
- **Weekend Multiplier** — Great for incentivising chores on days children have more free time. Set it to `1.5` for a gentler boost or `3.0` for a big incentive
- **Jackpot rewards** — Use these for big shared goals. A family holiday, a trip to a theme park, a new board game — something everyone works toward together
- **Header colours** — Each card has its own default colour. Customise them in the visual editor to make the children's dashboard bright and fun, and the parent dashboard more neutral
- **Per-chore sounds** — Set `completion_sound: fanfare` on harder chores to make completing them feel more rewarding than easy ones
- **Time-of-day cards** — Set `time_category: morning` on a card for the breakfast routine and `elapsed_time_mode: dim` so missed morning chores grey out automatically once it's afternoon — no clutter, no guilt trips
 
---
 
## Changelog
 
See [GitHub Releases](https://github.com/tempus2016/taskmate/releases) for the full changelog.
 
---
 
<p align="center">
  <sub>License: MIT · Data stays local in your Home Assistant instance</sub>
</p>
