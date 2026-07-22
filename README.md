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
 
> Originally created by [vinnybad/choremander](https://github.com/vinnybad/choremander). This fork adds 20 Lovelace cards, a bonus points system, streak tracking, reward approval flow, a penalty system, and much more.
 
---
 
## Contents
 
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Setup](#setup)
- [Chores & Rewards](#chores--rewards)
- [Chore Scheduling](#chore-scheduling)
- [Chore Dependencies](#chore-dependencies)
- [Dynamic Chore Visibility](#dynamic-chore-visibility)
- [Weather-Aware Chores](#weather-aware-chores)
- [Reactive Chores (Deadlines & Speed Bonus)](#reactive-chores-deadlines--speed-bonus)
- [Scheduled Config Changes](#scheduled-config-changes)
- [Routine Mode](#routine-mode)
- [Chore Roulette](#chore-roulette)
- [Timed Unlock Rewards](#timed-unlock-rewards)
- [Insights — Fairness, Friction, Week Ahead & Health](#insights--fairness-friction-week-ahead--health)
- [Pre-Reader Mode](#pre-reader-mode)
- [Read Aloud](#read-aloud)
- [Accessible Design Style](#accessible-design-style)
- [Multi-Parent Approval Routing](#multi-parent-approval-routing)
- [Sharing Template Packs](#sharing-template-packs)
- [Printable Weekly Chart](#printable-weekly-chart)
- [Guest Child Profiles](#guest-child-profiles)
- [Bonus Points System](#bonus-points-system)
- [Notifications](#notifications)
- [Quiet Hours](#quiet-hours)
- [Reminder Escalation](#reminder-escalation)
- [Weekly Digest & Monthly Report](#weekly-digest--monthly-report)
- [Penalties](#penalties)
- [Achievement Badges](#achievement-badges)
- [Timed Tasks](#timed-tasks)
- [Task Groups](#task-groups)
- [Quests](#quests)
- [Challenges](#challenges)
- [Leaderboard Seasons](#leaderboard-seasons)
- [Pool Mode (Savings Jars)](#pool-mode-savings-jars)
- [Family Goals](#family-goals)
- [Allowance (Real-Money Payouts)](#allowance-real-money-payouts)
- [Photo Proof](#photo-proof)
- [To-Do Lists](#to-do-lists)
- [Configuration Entities](#configuration-entities)
- [Voice Assistants](#voice-assistants)
- [Calendar Subscription (ICS Feed)](#calendar-subscription-ics-feed)
- [Automation Blueprints](#automation-blueprints)
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
 
## Chore Dependencies
 
Chain chores together so one only becomes available after others are finished. A chore with dependencies stays **locked** until **every** chore it depends on has been completed and approved **today** by the **same child** — then it unlocks for that child. This turns a loose list into an ordered routine: tidy the room *before* vacuuming, clear the table *before* loading the dishwasher.
 
- Set prerequisites in the chore editor (**Admin Panel → Chores → Edit chore**) via the **"Depends on"** picker — pick one or more of your other chores (stored as the chore's `depends_on` list). All selected prerequisites must be satisfied before the dependent chore unlocks.
- Each prerequisite needs an **approved** completion (a pending one doesn't count), made **today**, by the **same child**. Parent completions count; bonus sub-tasks do not.
- The check is **per day** — dependencies reset every night. If a prerequisite is rejected or its approval is undone, the dependent chore locks again.
- Dependencies are one more gate on top of scheduling, rotation, vacation status, and [Dynamic Chore Visibility](#dynamic-chore-visibility). While locked, the chore follows the same hide/dim child-card rules as any other unavailable chore.
 
See the [Chore Dependencies wiki page](https://github.com/tempus2016/taskmate/wiki/Chore-Dependencies) for full details.
 
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
 
## Weather-Aware Chores
 
Outdoor chores can hide themselves when the weather is unsuitable. Open a chore and expand **Advanced — weather conditions**.
 
| Setting | Effect |
|---|---|
| **Weather entity** | The `weather.*` entity to read. Leave empty to ignore the weather entirely. |
| **Hide when the weather is** | Any number of conditions — rainy, pouring, snowy, sleet, hail, lightning, thunderstorm, fog, windy, very windy, cloudy, severe. |
| **Minimum / maximum temperature** | Hide below / above this. Leave empty for no limit. |
| **Maximum wind speed** | Hide above this. Leave empty for no limit. |
 
Temperature and wind limits are read from the weather entity's `temperature` and `wind_speed` attributes, in whatever units your entity reports.
 
### Key Points
 
- **A rained-off chore is not a missed chore.** The check sits in the same availability path as scheduling, so a hidden chore does not raise a mandatory-miss review item and does not break a streak.
- **Fail-open.** A missing entity, an `unavailable`/`unknown` state, or an absent attribute all leave the chore visible. A weather integration going offline never hides the family's chores.
- **0 is a real limit.** Leave a limit blank to disable it — `0` means 0°, not "off".
- Conditions are checked first, then temperature, then wind.
 
### Common Use Cases
 
- Mow the lawn — hide on `rainy` and `pouring`
- Wash the car — hide below 2°
- Put the bins out — hide above 40 km/h wind
- Water the plants — hide on `rainy` (nature did it for you)
 
---
 
## Reactive Chores (Deadlines & Speed Bonus)
 
A chore raised by an automation that must be done *now*: "the washing machine finished — empty it within 30 minutes."
 
Call `taskmate.add_chore` with `expires_in_minutes`:
 
```yaml
triggers:
  - trigger: state
    entity_id: sensor.washing_machine_status
    to: "finished"
actions:
  - action: taskmate.add_chore
    data:
      name: Empty the washing machine
      points: 10
      assigned_to: ["<child_id>"]
      requires_approval: false
      expires_in_minutes: 30
      speed_bonus_points: 5
```
 
| Field | Effect |
|---|---|
| `expires_in_minutes` | Deadline this many minutes from now. `0` = no deadline (a normal chore). Max 10080 (a week). |
| `speed_bonus_points` | Extra points if the chore is completed before the deadline. |
 
### How It Works
 
- A chore with a deadline is automatically **one-shot** — it exists to be done now and never carries into tomorrow.
- The child card shows a live **countdown badge** — amber, turning red under five minutes — with the speed bonus alongside it.
- Beat the deadline and `speed_bonus_points` is added on top of the normal award. This **stacks** with the early-bonus/late-penalty of `due_time` if the chore has one.
- Miss it and the chore disappears and is soft-disabled. The sweep runs on the 30-second poll, so a 30-minute chore doesn't sit on the card until midnight.
- Expiry fires a `taskmate_chore_expired` event (`chore_id`, `chore_name`, `deadline_at`, `timestamp`) so an automation can nag, re-raise it, or just log the miss.
 
---
 
## Scheduled Config Changes
 
Queue an edit to take effect on a future date — *"from 1 September this chore is worth 20 points"*, *"from November it's disabled for the winter"*.
 
Open a chore in the TaskMate panel and expand **Advanced — scheduled changes**. Pick a date, a field, and the new value. Queued changes are listed with a count badge on the section, and can be removed before they fire.
 
### What Can Be Scheduled
 
Points · Assigned to · Enabled · Requires approval · Daily limit · Days · Mandatory · Penalty points · Expires on · Description · Time of day · Difficulty
 
Runtime state (rotation anchors, skip dates, calendar publish history) deliberately **cannot** be scheduled — a queued change can only touch configuration.
 
### How It Works
 
- Changes are applied during **midnight maintenance**.
- **Missed days catch up.** If Home Assistant was off on the day a change was due, it's applied on the next start — the parent still expects "from 1 September" to have happened.
- **Values are validated when you queue them**, not at midnight weeks later, so a bad value fails in front of you.
- The date must be in the future. Today is rejected, because it would actually fire at the *next* midnight — a day later than it reads.
- **Applied changes are kept**, not deleted, and shown under "Already applied". A config change that happens silently is worse than one that doesn't happen at all.
- Applying fires a `taskmate_scheduled_change_applied` event (`change_id`, `chore_id`, `chore_name`, `changes`, `timestamp`).
- Deleting a chore removes its queued changes.
 
---
 
## Routine Mode
 
A guided, one-task-at-a-time flow for morning and bedtime routines. The child card is a checklist — good for scanning, poor for walking a five-year-old through getting ready. Routine mode shows a single task at a time with a big **Done** button, a progress bar and a celebration at the end.
 
Add the **TaskMate Routine** card:
 
```yaml
type: custom:taskmate-routine-card
entity: sensor.taskmate_overview
child_id: <child_id>
time_category: morning     # morning | afternoon | evening | night | anytime | all
title: Vaiha's morning     # optional
```
 
| Control | Effect |
|---|---|
| **Done** | Completes the chore and moves to the next one. |
| **Skip for now** | Moves on without completing — the task stays outstanding. |
| **Back** | Returns to the previous task, so a mis-tap is recoverable. |
 
### Key Points
 
- Availability comes from the integration's own chore-availability matrix, so the weather gate, reactive deadlines, dependencies, rotation and vacation mode are all honoured automatically.
- Tasks appear in the child's configured chore order.
- **`time_category` is exact.** A `morning` routine shows only morning chores — `anytime` chores are *not* mixed in, because a routine is a specific sequence. Use `all` if you want everything.
- Chores needing approval show "waiting for a grown-up" and their points are totalled separately on the finish screen.
- The finish screen totals what was earned **in that run**, not the whole day.
- An empty period shows a "nothing to do" state rather than an empty list.
 
---
 
## Chore Roulette
 
An opt-in nudge for the child who has stalled: spin once, get a random outstanding chore, and earn a multiplier on it if they do it.
 
Enable it in **Settings** (off by default) and set the multiplier and how many spins a child gets per day. Then add `show_roulette: true` to a child card:
 
```yaml
type: custom:taskmate-child-card
entity: sensor.taskmate_overview
child_id: <child_id>
show_roulette: true
```
 
### Key Points
 
- **Doubly opt-in.** It needs both the global setting *and* `show_roulette: true` on the card, so an existing dashboard never sprouts a new button unasked.
- Roulette only ever picks a chore the child is **actually allowed to do right now** — it runs the same availability check as everything else, so the weather gate, deadlines, dependencies and rotation are all respected.
- The pick is recorded **per child, per day**. It survives a reload, can't be re-rolled past the daily allowance, and expires overnight.
- A re-spin moves to a different chore where one is available, rather than handing back the same one.
- The multiplier is applied at completion, and **stacks** with the difficulty multiplier and any speed bonus.
- Spinning fires `taskmate_roulette_spun` (`child_id`, `child_name`, `chore_id`, `chore_name`, `multiplier`, `timestamp`).
- A multiplier below 1 is clamped to 1 — spinning should never punish the child.
 
Children spin via the `taskmate.spin_roulette` service (`child_id`), which the card calls for them.
 
---
 
## Timed Unlock Rewards
 
Spend points to unlock something for a while — the TV, the console socket, a wifi group. Approving the claim turns the entity on; a timer turns it back off.
 
**Two deliberate limits** keep this from becoming "a reward can do anything to your house":
 
1. A reward can only **turn one entity on and back off**. There is no free-form service call, no payload, no template.
2. The entity must be on your **allowlist**.
 
### Setting It Up
 
1. **Settings → Unlock allowlist** — add the entities a reward may touch. An entry can be a full entity id (`switch.xbox`) or a bare domain (`switch`) to permit everything in it. **An empty allowlist permits nothing** — this gates household devices, so the safe default when unconfigured is "no".
2. Open a reward, expand **Advanced — timed unlock**, pick an allowlisted entity and a duration (up to 24 hours; `0` leaves it on for you to turn off yourself).
 
### Key Points
 
- The allowlist is checked **when the reward is saved and again when it fires** — you can revoke an entity later and any reward pointing at it quietly stops unlocking rather than breaking.
- Active unlocks are **persisted**. A Home Assistant restart mid-unlock re-arms the timer; anything already past due is turned off at startup. A restart can never strand the television on.
- Turning something **off** is never gated by the allowlist — a revert is always safe.
- Fires `taskmate_unlock_started` and `taskmate_unlock_ended` (`entity_id`, `reward_id`, `reward_name`, `child_id`, `child_name`, `started_at`, `revert_at`).
 
---
 
## Insights — Fairness, Friction, Week Ahead & Health
 
**TaskMate panel → Insights.** Answers the question the raw numbers don't: *am I dumping everything on the eldest?*
 
For a chosen window (7, 14 or 30 days) it shows each child's completed chores, points earned, share of the family total, and how many distinct days they were active — with a marker showing where an even split would sit.
 
### Key Points
 
- **Judged on chore count, not points.** A pricier chore shouldn't be able to hide an uneven split. Points are shown alongside because the two can disagree: three quick jobs versus one hard one is balanced by points and lopsided by count, and only you can say which you meant.
- Flagged as *doing more* / *doing less* when a child is more than **15 percentage points** off an even share. Wide enough that normal week-to-week variation doesn't nag; narrow enough to catch a real imbalance.
- **Only approved, non-bonus completions count.** Unapproved work isn't yet work you've agreed happened, and bonus sub-tasks hang off a chore that's already counted.
- Computed on demand, never cached — a stale report is worse than a slow one.
 
### Friction — what isn't working
 
The second Insights view judges each **chore** rather than each child: how often it actually gets done versus how often it came up, over 14 / 30 / 90 days.
 
| Verdict | Meaning | Suggestion |
|---|---|---|
| **Never done** | No completion on record, ever | Retire it |
| **Stalling** | Done under 20% of the time it came up | Retire if long dead, otherwise raise the points or reassign |
| **Patchy** | Done 20–60% of the time | Raise the points |
| **Fine** | Done 60%+ of the time | Leave it alone |
 
Chores with outstanding mandatory misses show a ⚠ count, and the report leads with a **suggestion** rather than just a diagnosis — a stalling chore that already pays well doesn't need more points, it needs a different child.
 
**What it can't tell you:** TaskMate deletes a completion when you reject it, and removes a mandatory miss once you resolve it, so neither rejection counts nor historical miss counts exist to be reported. The report says so rather than quietly omitting them. Expected counts are approximate — they don't replay rotation, dependencies, weather or vacations.
 
### Week ahead — what's coming up
 
The third view projects the next 7 / 14 / 28 days from each chore's schedule: how many chores and points are heading each child's way, what balance they'd reach, and a day-by-day grid.
 
Rotation is projected using the same daily-assignment computation the integration itself uses, so alternating / random / balanced picks match what will really happen rather than an independent guess that could drift.
 
**It's a ceiling, not a forecast.** A chore open to everyone is counted for *each* eligible child, because the schedule cannot know who'll get there first. Weather, dependencies and availability aren't projected either — they depend on the day. Points that aren't assigned to anyone are called out separately.
 
### Health — is anything broken?
 
The fourth view checks the setup itself and reports storage size and entity counts.
 
| Check | Severity |
|---|---|
| A chore depends on a chore that no longer exists (it can never unlock) | **Error** |
| A chore or reward is assigned to a deleted child | Warning |
| A chore references a visibility/weather entity that doesn't exist | Warning |
| A reward unlocks an entity no longer on the allowlist (nothing will happen) | Warning |
| A child has no chores; completion records for deleted chores; a very large history | Note |
 
Every issue carries a plain sentence and a **Show me** button that jumps to where it lives — a diagnostic that only says "3 problems" isn't one you can act on. Notes alone still count as healthy.
 
---
 
## Pre-Reader Mode
 
A picture-only child card for children who can't read yet. No chore names, no numbers — a big icon, a row of stars for the points, and a huge tick when it's done.
 
```yaml
type: custom:taskmate-child-card
entity: sensor.taskmate_overview
child_id: <child_id>
pre_reader: true
pre_reader_labels: false   # optional; adds the chore name back under each tile
```
 
### Key Points
 
- **Chores now have a picture.** Set one per chore in the panel (next to the description). Without it a tile falls back to the time-of-day icon — fine for one chore, useless for telling "brush teeth" from "get dressed", so set them.
- **Points are shown as stars, not digits** (1–5, scaled from the chore's value). A four-year-old can count pictures.
- Tiles are at least 128 px with a large tap target, and a **done tile stays tappable** so a mis-tap can be undone, exactly as on the standard card.
- **Opt-in.** An existing dashboard never turns into pictures on its own, and names stay off unless you ask for them.
 
---
 
## Read Aloud
 
Speak a child's outstanding chores to a media player — *"Ella, you have three things left: make your bed, brush your teeth and pack your bag."*
 
```yaml
action: taskmate.read_aloud
data:
  child_id: <child_id>
  media_player: media_player.kitchen   # optional; falls back to the Settings default
  tts_entity: tts.piper                # optional; falls back to Settings, then the only one installed
  message: "Dinner is ready"           # optional; says this instead of the summary
```
 
### Wording
 
The sentence comes from **parent-editable templates** in Settings, not from TaskMate's translations. The frontend locales don't reach the backend, and a family may well want phrasing that isn't one of the eight shipped languages.
 
| Setting | Default | Placeholders |
|---|---|---|
| `read_aloud_template` | `{name}, you have {count} things left: {chores}.` | `{name}` `{count}` `{chores}` |
| `read_aloud_one_template` | `{name}, you have one thing left: {chores}.` | same |
| `read_aloud_done_template` | `{name}, you're all done. Nice one!` | same |
| `read_aloud_joiner` | `and` | joins the last two chores |
 
A template with a bad placeholder logs a warning and falls back to the built-in wording rather than silencing the feature.
 
Fires `taskmate_read_aloud` (`child_id`, `media_player`, `tts_entity`, `message`).
 
---
 
## Accessible Design Style
 
A fifth per-card design alongside Classic, Playroom, Console and Clean Pro — pick it per card or as the global default.
 
- **Colour-blind safe.** Uses the Okabe-Ito palette, which stays distinguishable under protanopia, deuteranopia and tritanopia.
- **High contrast.** Near-black on white (~19:1, comfortably past WCAG AAA), with heavy borders so meaning never rests on hue alone.
- **Dyslexia-friendly type.** Atkinson Hyperlegible, drawn for low vision — its letterforms stay distinct where similar glyphs (I/l/1, O/0) usually collapse.
- **Dark variant included.** `#0A0A0A` rather than pure black, which blooms on OLED and is harsh with astigmatism.
 
---
 
## Multi-Parent Approval Routing
 
By default every approval buzzes every parent. Two other modes are available via the `parent_routing` setting:
 
| Mode | Behaviour |
|---|---|
| `all` *(default)* | Every enabled parent, as before |
| `home` | Only parents whose presence entity says they're here |
| `round_robin` | One parent per notification, rotating |
 
Give each parent a **presence entity** (`device_tracker.*`, `person.*`, anything that reads `home`/`on`/`true`/`present`) in the notification settings.
 
### Every fallback errs towards over-notifying
 
An unseen approval is worse than a redundant buzz, so:
 
- **Nobody home** → everyone is told, not nobody.
- **No presence entity set** → that parent counts as available and is never silently cut out.
- **Broken or unavailable presence sensor** → fails open.
- **Round-robin state pointing at a deleted parent** → starts from the beginning rather than wedging.
 
Round-robin position is tracked **per notification type**, so a reward claim doesn't advance the chore-approval rotation. Child notifications are never affected by any of this — a reminder for a child must always reach that child.
 
---
 
## Sharing Template Packs
 
Export your custom chore templates as a JSON pack and import one somebody else made.
 
- **Export** — `taskmate/templates/export` returns a pack (all custom templates, or a chosen subset). Built-ins are excluded: they ship with TaskMate, so exporting them would only create duplicates on the other end.
- **Import** — `taskmate/templates/import` takes a pack object.
 
### Import is treated as untrusted
 
A pack is arbitrary JSON from someone else, so:
 
- **Unknown chore fields are dropped**, not carried through. A shared pack cannot set runtime state (rotation anchors, skip dates) or anything the panel wouldn't let you set by hand.
- Format and version are checked. A pack from a newer TaskMate says so plainly rather than being half-imported.
- Sizes are capped (50 templates, 200 chores each) and long names truncated rather than rejected.
- **A clashing name is suffixed, never overwritten** — `Morning routine (2)`. An import must not silently replace something your family built.
- A pack that fails validation writes **nothing**.
 
**No URL importing.** Packs are imported from pasted or uploaded JSON only. Fetching arbitrary URLs from inside your home network would make TaskMate an SSRF vector; you can still paste a gist's raw contents.
 
---
 
## Printable Weekly Chart
 
A fridge-ready A4 chore chart with a box to tick against every task.
 
`taskmate/print/weekly_chart` returns a **standalone HTML page** — open it in a tab and print. No external assets, so it prints identically offline.
 
| Option | Values |
|---|---|
| `orientation` | `portrait` *(default)* or `landscape` — **your choice**: two children with short names fit portrait, five need the width |
| `week_start` | ISO date anywhere in the week you want (defaults to this week) |
| `title` | Heading text (defaults to "This week") |
 
### Key Points
 
- **Schedule only.** A paper chart can't know next Thursday's weather, so entity-driven gates aren't applied — a chart that quietly omitted a chore would be worse than one that lists it.
- Chores with no assignee appear for every child; assigned ones only for theirs.
- Children with nothing assigned are left off entirely rather than printing an empty row.
- Chore names are HTML-escaped: they're user input landing in a document.
 
---
 
## Guest Child Profiles
 
A visiting cousin gets a temporary child profile that expires on its own and stays out of the family leaderboard.
 
Set **Guest** and an end date on a child (`is_guest`, `guest_expires_on`).
 
### Key Points
 
- **Guests don't compete.** They're excluded from the leaderboard — a cousin here for a week shouldn't win the month, and their leaving shouldn't read as a loss.
- **No end date means no expiry.** You may not know how long the visit is, and silently archiving someone mid-stay would be worse than leaving the profile up.
- **Expired guests are archived, not deleted.** The visit's completions stay in history, and next summer the same guest can be reactivated rather than rebuilt. Archiving reuses the existing availability plumbing, so every chore and streak path already treats them as away.
- **Promoting a guest to a family member** clears the end date and un-archives them — someone who moves in shouldn't stay invisible.
- Archiving fires `taskmate_guest_archived`.
 
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
- Enable **Perfect week needs all tasks** to require *every* chore due that day to be done (not just one) before the day counts

> **Stricter streaks:** the matching **Streak needs all tasks** toggle applies the same rule to daily streaks — a day only extends the streak once every chore due that day is complete. Both default to off, preserving the original "any one chore" behaviour.
 
### Settings Reference
 
| Setting | Default | Description |
|---------|---------|-------------|
| Weekend Points Multiplier | `2.0` | Multiplier on Sat/Sun (1.0 = off) |
| Streak Milestone Bonuses | `on` | Master toggle |
| Streak Milestone Configuration | `3:5, 7:10, 14:20, 30:50, 60:100, 100:200` | Custom `days:points` pairs |
| Streak needs all tasks | `off` | Only extend a streak once every chore due that day is done |
| Perfect Week Bonus | `on` | Toggle |
| Perfect Week Bonus Points | `50` | Points per perfect week |
| Perfect week needs all tasks | `off` | A day counts only when every chore due that day is done |
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
 
## Quiet Hours
 
Set a per-child do-not-disturb window so TaskMate doesn't ping a child during school or after bedtime. While a child's local time is inside their window, **that child's** notifications are silently held back. Parent notifications are never affected.
 
- Set the window per child in the **Admin Panel → Notifications** tab — a **Quiet hours** start and end time alongside each child's notify service. Fill in **both** (`quiet_hours_start` / `quiet_hours_end`, 24-hour `HH:MM`) to enable; clear either to turn it off.
- The **end is exclusive**; an equal start and end is treated as disabled.
- If the start is later than the end, the window runs **overnight** (e.g. `20:00`–`07:00` covers the evening through to the next morning). Earlier start than end is a same-day window (e.g. `08:30`–`15:30` for the school day).
 
See the [Quiet Hours wiki page](https://github.com/tempus2016/taskmate/wiki/Quiet-Hours) for full details.
 
---
 
## Reminder Escalation
 
When a mandatory chore is left incomplete, TaskMate can step up its reminders instead of staying silent. Each open same-day mandatory miss climbs a three-rung ladder:
 
| Stage | Fires | Audience | When |
|---|---|---|---|
| 1 — Nudge | `mandatory_reminder` | The child | As soon as the miss is raised |
| 2 — Reminder | `mandatory_reminder` | The child | After the **reminder** threshold |
| 3 — Parent alert | `mandatory_parent_alert` | Parents | After the **parent** threshold |
 
- The two thresholds, both in minutes from when the miss was raised, are set in the **Admin Panel → Notifications** tab under the mandatory-reminder controls: `mandatory_escalation_reminder_minutes` (default `30`) and `mandatory_escalation_parent_minutes` (default `120`), each 1–1440.
- The child rungs go only to the affected child (and respect [Quiet Hours](#quiet-hours)); the parent alert goes to the routed parent recipients and is never suppressed.
- Both notification types are **off by default** — enable and route the **Mandatory reminder** and **Mandatory parent alert** types. If the child completes the chore, that miss stops climbing.
 
See the [Reminder Escalation wiki page](https://github.com/tempus2016/taskmate/wiki/Reminder-Escalation) for full details.
 
---
 
## Weekly Digest & Monthly Report
 
TaskMate can send parents a periodic recap of each child's activity.
 
- **Weekly digest** (`weekly_digest`) — fires **Sundays at 18:00**, one line per child showing chores completed and points earned this week (approved completions only; bonus subtasks and pending completions excluded).
- **Monthly report** (`monthly_report`) — fires on the **1st of each month at 18:00**, recapping the **previous calendar month** per child: chores completed, points earned, level, and best streak.
 
Both have the **parent** audience, deliver through the standard notification system, and are **off by default**. Enable and route the **Weekly digest** / **Monthly report** types on the Notifications tab, and use **Send test** to verify routing without waiting for the schedule.
 
See the [Weekly Digest wiki page](https://github.com/tempus2016/taskmate/wiki/Weekly-Digest) for full details.
 
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

## Leaderboard Seasons

Leaderboard Seasons turn the leaderboard into a fresh monthly contest. Each child builds up **season points** over the current calendar month; on the 1st of the next month the season finalizes, a champion is recorded, and everyone's season total resets to zero — so every child gets a fresh shot each month.

- Season points accumulate from **positive point gains only** during the current month (approved chores, bonuses, other awards). Penalties and deductions never pull a season score down.
- The running total is exposed per child on `sensor.taskmate_overview` as `season_points`, with the current month in `season_month` (`YYYY-MM`).
- When the month rolls over, the top child is appended to `season_champions` history and a `season_champion` notification announces the winner. If nobody earned points, no champion is recorded.
- Show it on the [Leaderboard Card](#leaderboard-card) with `sort_by: season` — children rank by season points and the card shows a champion banner. Other sort modes leave season tracking running in the background.

```yaml
type: custom:taskmate-leaderboard-card
entity: sensor.taskmate_overview
sort_by: season               # points | streak | weekly | career | season
header_color: "#b7950b"
```

See the [Leaderboard Seasons wiki page](https://github.com/tempus2016/taskmate/wiki/Leaderboard-Seasons) for full details.

---

## Pool Mode (Savings Jars)

Children can save up for expensive rewards over time by depositing points into a dedicated savings pool. Points are locked once deposited — there is no withdrawal.

- Enable pool mode per reward in the admin panel
- Children deposit points via the Rewards Card or `taskmate.allocate_points_to_pool`
- Once the pool reaches the reward cost, the child can claim it

See the [Pool Mode wiki page](https://github.com/tempus2016/taskmate/wiki/Pool-Mode-(Savings-Jars)) for full details.

---

## Family Goals

A Family Goal is a single shared target the whole family works toward together — *"when we reach 500 points between us, we have a movie night"*. Instead of each child chasing their own rewards, **everyone's points are summed** against one combined target. It's co-operative rather than competitive, and parent-controlled.

Family Goals are opt-in. Enable in the panel's **Settings → Family goal** section: set **Enable family goal** (`family_goal_enabled`), a **Goal name**, a **Target** combined-points figure (`family_goal_target`, default `500`), and the **Reward** the family earns.

- Progress is simply the **sum of every child's current points** — there are no deposits to make (unlike [Pool Mode](#pool-mode-savings-jars)). The total moves up and down as children earn and spend.
- When the combined total first reaches the target, TaskMate fires a one-time **Family goal reached** notification and a `taskmate_family_goal_reached` event. Changing the target (or toggling the goal off and on) resets the reached state so it can be celebrated afresh.
- Add the **Family Goal Card** to a dashboard for live progress. The card reads the overview sensor's `family_goal` attribute.

See the [Family Goals wiki page](https://github.com/tempus2016/taskmate/wiki/Family-Goals) for full details.

---

## Allowance (Real-Money Payouts)

Allowance turns saved-up points into a real-money pocket-money payout. When a child cashes in points, you record the payout: TaskMate deducts the points and writes a cash entry — in your currency — into a payout ledger you can review later. It is **parent-controlled** and uses a **fixed conversion rate** — a point is always worth the same amount.

Allowance is opt-in. Enable in the panel's **Settings → Allowance** section: switch **Enable allowance payouts** (`allowance_enabled`) on, set **Points per unit** (`allowance_rate`, default `10` — how many points equal one unit of currency), and a **Currency symbol** (`allowance_currency`, e.g. `£` or `$`).

Record a payout with the `record_allowance_payout` service — typically from a weekly automation or a dashboard button:

```yaml
service: taskmate.record_allowance_payout
data:
  child_id: a8c8376a
  points: 50                  # 1–100000; with a rate of 10 this pays out 5.00
```

When it runs, the points are **deducted** (logged as `Allowance payout`), a cash amount of `points ÷ rate` (rounded to 2 dp) is recorded in your currency, a ledger entry is appended (capped at the most recent 500, shown in the panel's Allowance section), and a `taskmate_allowance_paid` event is fired. The service is **admin-gated** and rejected if allowance is disabled, the child is unknown, or `points` is below 1.

See the [Allowance wiki page](https://github.com/tempus2016/taskmate/wiki/Allowance) for full details.

---

## Photo Proof
 
Evidence photos are attached to the **approval push notification** on the HA companion app, so a parent can approve from the lock screen while actually looking at the tidied room. The URL is signed (24h) because the app fetches attachments without the user's bearer token — an unsigned URL returns 401. Android reads `data.image` and iOS reads `data.attachment.url`; both are sent so one payload works on either. Non-mobile backends (Telegram, email, persistent) get no attachment, since they'd render a raw payload rather than a picture.
 

Photo proof lets a chore require evidence before it counts. Turn on **Require photo proof** (`require_photo`) in the chore dialog and that chore's completions **always** go through parent approval — even if Requires Approval is off — and any photo attached is shown to the parent as a thumbnail when they review it.

- Attach a photo at completion time via the `photo_url` field on `taskmate.complete_chore` — a URL or path to an image, e.g. a camera snapshot from an automation. The photo is optional; the requirement forces *approval*, while the photo is the evidence.

```yaml
service: taskmate.complete_chore
data:
  chore_id: b3f9a12c
  child_id: a8c8376a
  photo_url: /local/snapshots/dishwasher.jpg
```

- The thumbnail renders in the Admin Panel approvals list, the [Approvals Card](#approvals-card), and the [Parent Dashboard](#parent-dashboard-card) card; clicking it opens the full image. The photo URL is signed so it loads without extra authentication.
- To browse past evidence, add the **Photo Gallery Card** — a grid of every proof photo, each captioned with the child, chore, and date.

See the [Photo Proof wiki page](https://github.com/tempus2016/taskmate/wiki/Photo-Proof) for full details.

---

## To-Do Lists

TaskMate publishes each child's outstanding chores as a native Home Assistant **to-do list** — `todo.taskmate_<child name>` (e.g. `todo.taskmate_malia`) — so you can see and tick off today's chores using HA's built-in To-do List card and any voice assistant, without the custom TaskMate cards. New children get their own list automatically.

Each list shows the chores that child **still needs to do today** (it shares the integration's due-chore logic, so vacation mode, scheduling, availability, and dynamic visibility are honoured). **Checking an item off completes the chore** for that child — points are awarded and the usual approval flow applies. You don't add chores from the to-do card; create them in the Admin Panel.

```yaml
type: todo-list
entity: todo.taskmate_malia
```

See the [To-Do Lists wiki page](https://github.com/tempus2016/taskmate/wiki/To-Do-Lists) for full details.

---

## Configuration Entities

A handful of TaskMate's most useful settings are also exposed as standard Home Assistant **number** and **select** entities, so you can read or change them straight from the HA UI or from an automation — without opening the Admin Panel. These entities and the panel are two views of the **same** stored settings.

| Entity | Range / Options | Controls |
|--------|-----------------|----------|
| `number.taskmate_weekend_multiplier` | 1.0–5.0, step 0.5 | Weekend points multiplier (1.0 = off) |
| `number.taskmate_perfect_week_bonus` | 0–1000 | Points for a perfect week |
| `select.taskmate_streak_reset_mode` | `reset`, `pause` | What happens when a child misses a day |
| `select.taskmate_card_design` | `classic`, `playroom`, `console`, `cleanpro` | Global default card style |

```yaml
# e.g. raise the weekend multiplier during a holiday week
action: number.set_value
target:
  entity_id: number.taskmate_weekend_multiplier
data:
  value: 2.0
```

See the [Configuration Entities wiki page](https://github.com/tempus2016/taskmate/wiki/Configuration-Entities) for full details.

---

## Voice Assistants

TaskMate adds Home Assistant **conversation intents** so you can ask Assist — by voice or text — about your children's chores and points:

- *"How many chores does Malia have left?"* → `TaskMateChoresLeft`
- *"How many stars does Alex have?"* → `TaskMatePoints`

The intent handlers register automatically. The **trigger sentences** are not automatic — copy TaskMate's example file from the repo (`custom_sentences/en/taskmate.yaml`) into your config at `<config>/custom_sentences/en/taskmate.yaml`, then restart Home Assistant. For other languages, copy it under the matching language code and translate only the `sentences:` lines.

The per-child [to-do lists](#to-do-lists) also work with voice assistants for free — you can ask what's on a child's list and tick items off by voice.

See the [Voice Assistants wiki page](https://github.com/tempus2016/taskmate/wiki/Voice-Assistants) for full details.

---

## Calendar Subscription (ICS Feed)

Alongside the per-child HA calendar entities (`calendar.taskmate_<child>`), TaskMate can publish your upcoming chores as a single subscribable **ICS feed** you can add to Google Calendar, Apple Calendar, Outlook, or any app that accepts a calendar URL — so a parent or child can see upcoming chores in their everyday calendar app without opening HA.

The feed is served read-only at:

```
/api/taskmate/calendar.ics?token=<token>
```

- Find the subscribe URL in the **Admin Panel → Settings → Calendar subscription** section — click **Show subscribe link**, then **Copy**. It covers the same horizon as the calendar entities (the **Calendar projection** setting).
- The link is **token-protected** and public-by-link, so treat it like a private link. If it's ever shared too widely, click **Regenerate link** to issue a new URL and immediately invalidate the old one (any app still subscribed to the previous link must be re-subscribed).

See the [Calendar wiki page](https://github.com/tempus2016/taskmate/wiki/Calendar) for full details.

---

## Automation Blueprints

TaskMate ships a set of ready-made Home Assistant **automation blueprints** so you can react to common TaskMate moments without writing the trigger and condition logic yourself. Each fires on a TaskMate bus event and lets you pick the action to run.

| Blueprint | Fires on | Use it for |
|-----------|----------|-----------|
| `chore_completed.yaml` | `taskmate_chore_completed` | Reward a completed chore — flash a light, play a chime, post a message |
| `level_up.yaml` | `taskmate_level_up` | Celebrate when a child reaches a new XP level |
| `reward_approved.yaml` | `taskmate_reward_approved` | React when a reward claim is approved |
| `mandatory_missed.yaml` | `taskmate_mandatory_missed` | React when a mandatory chore's window closes incomplete |

The first three accept an optional **Only this child** name (blank = all children). Import via **Settings → Automations & scenes → Blueprints → Import blueprint** with the blueprint's raw URL, e.g. `https://github.com/tempus2016/taskmate/blob/main/blueprints/automation/taskmate/chore_completed.yaml`.

See the [Automations wiki page](https://github.com/tempus2016/taskmate/wiki/Automations) for full details.

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
| [Family Goal Card](#family-goal-card) | Both | Live progress toward a shared family-wide points goal |
| [Photo Gallery Card](#photo-gallery-card) | Parents | Grid of proof photos from chore completions |
 
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
show_undo: true               # optional — set false to hide undo buttons (kid-friendly dashboards)
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
sort_by: points               # points | streak | weekly | career | season
show_streak: true
show_weekly: true
header_color: "#b7950b"
```

> **Seasons:** set `sort_by: season` to rank children by their points for the current calendar month and show a champion banner naming the most recent monthly winner. See [Leaderboard Seasons](#leaderboard-seasons).

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

### Family Goal Card

Live progress toward a shared [Family Goal](#family-goals) — a progress bar, the combined family total against the target, the percentage, and the reward. When the goal is reached the card switches to a trophy and a celebration message. If no family goal is enabled, it shows a quiet "No family goal set" placeholder. Reads the overview sensor's `family_goal` attribute.

```yaml
type: custom:taskmate-family-goal-card
entity: sensor.taskmate_overview
title: Movie Night Fund       # optional — defaults to the goal name
header_color: "#16a085"
```

---

### Photo Gallery Card

Grid of thumbnails for every chore completion that carried a [photo-proof](#photo-proof) image, each captioned with the child, the chore, and the date. Tap a thumbnail to open the full image in a new tab; completions still awaiting approval are marked **pending**. Backed by the `photo_gallery` attribute on the **activity** sensor — note this card uses `sensor.taskmate_activity` as its entity.

```yaml
type: custom:taskmate-photo-gallery-card
entity: sensor.taskmate_activity
title: Proof Photos           # optional
max: 40                       # optional — limit the number of photos shown
header_color: "#5d6d7e"
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
| `taskmate.record_allowance_payout` | `child_id`, `points` | Deduct points and log a fixed-rate real-money payout in the allowance ledger (admin-only) |

**Example — record an allowance payout:**

```yaml
service: taskmate.record_allowance_payout
data:
  child_id: a8c8376a
  points: 50                  # 1–100000; deducted and logged at the fixed allowance rate
```

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
| `sensor.taskmate_overview` | total children | `children` summary (incl. per-child `season_points`), `points_name`, `points_icon`, `today_day_of_week`, totals, streak / perfect-week settings, `family_goal`, `season_month`, `season_champions` |
| `sensor.taskmate_chores` | total chores | `chores` list (definitions), `todays_completions` |
| `sensor.taskmate_chore_availability` | total chores available today | `chore_availability`: `{chore_id: {child_id: bool}}` |
| `sensor.taskmate_rewards` | total rewards | `rewards`, `pending_reward_claims`, `pool_allocations` |
| `sensor.taskmate_activity` | total completions all-time | `recent_completions` (last 35), `recent_transactions` (last 20), `photo_gallery` |
| `sensor.taskmate_incentives` | penalties + bonuses count | `penalties`, `bonuses` |
| `sensor.taskmate_pending_approvals` | pending approvals count | `chore_completions`, `reward_claims` (detailed lists) |
| `sensor.taskmate_<child>_points` | points for that child | `child_id`, `current_streak`, `best_streak`, `total_*` |
| `sensor.taskmate_<child>_stats` | chores completed by that child | `assigned_chores`, streak / totals |

Automations that read the old overview attributes (e.g. `sensor.taskmate_overview.attributes.chores`) should instead read from the matching companion sensor listed above.

### Other Platforms

Beyond the sensors above, TaskMate also exposes:

| Entity | What it is |
|---|---|
| `todo.taskmate_<child>` | One native HA to-do list per child of today's outstanding chores — tick an item to complete the chore. See [To-Do Lists](#to-do-lists) |
| `calendar.taskmate_<child>` | One read-only HA calendar per child of upcoming chore occurrences and away days |
| `number.taskmate_weekend_multiplier` | Weekend points multiplier (1.0–5.0). See [Configuration Entities](#configuration-entities) |
| `number.taskmate_perfect_week_bonus` | Perfect-week bonus points (0–1000) |
| `select.taskmate_streak_reset_mode` | Streak reset mode (`reset` / `pause`) |
| `select.taskmate_card_design` | Global default card design (`classic` / `playroom` / `console` / `cleanpro`) |
 
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
 
### v5.0.1
 
A bug-fix release. All of v5.0.0's new features work as documented; upgrade is drop-in with no configuration changes.

**Fixes**
- **The admin panel's Audit log is reachable again** — the Audit view was fully built but missing from the sidebar navigation, so there was no way to open it. It now appears in the panel's **System** group. ([#726](https://github.com/tempus2016/taskmate/pull/726))
- **Narrow-width layout fixes in the admin panel** — on a phone the Parent Dashboard card lost its **Points** tab off the edge (it now wraps), entity-id chips tore across two lines (they now truncate cleanly), and the pending-approvals pill is a larger tap target. ([#726](https://github.com/tempus2016/taskmate/pull/726))
- **Chore roulette now shows on every card design** — the spin button rendered on the Classic child card only. It now appears under Playroom, Console, Clean Pro and Accessible too, taking each design's accent colour. ([#728](https://github.com/tempus2016/taskmate/pull/728))
- **Pre-reader mode now works on every card design** — `pre_reader: true` was silently ignored on any style but Classic. The picture tiles now render under all five designs, so pre-reader pairs correctly with the Accessible style. ([#728](https://github.com/tempus2016/taskmate/pull/728))
- **The Photo Gallery and Family Goal cards now follow `card_design`** — both cards ignored the design setting and always rendered in the Classic look. They now take the active design's colours and fonts like every other card. ([#731](https://github.com/tempus2016/taskmate/pull/731))
- **The avatar picker works on every card design** — tapping a child's avatar to switch it worked on the Classic child card only. It now opens under all five designs. ([#731](https://github.com/tempus2016/taskmate/pull/731))
 
### v5.0.0
 
The largest release so far: fourteen new features across chores, rewards, cards, notifications and the admin panel. Nothing is removed and no configuration changes — existing setups upgrade untouched. The major version marks the size of the addition, not a breaking change.

**New — chores**
- **Weather-aware chores** — outdoor chores hide themselves when the weather is unsuitable. Open a chore and expand **Advanced — weather conditions** to pick the conditions it needs. ([#692](https://github.com/tempus2016/taskmate/pull/692))
- **Reactive chores with deadlines and a speed bonus** — a chore raised by an automation that must be done *now*: "the washing machine finished — empty it within 30 minutes." Beat the deadline and the child earns a bonus. ([#693](https://github.com/tempus2016/taskmate/pull/693))
- **Scheduled config changes** — queue an edit to take effect on a future date: *"from 1 September this chore is worth 20 points"*, *"from November it's disabled for the winter"*. ([#694](https://github.com/tempus2016/taskmate/pull/694))
- **Chore roulette** — an opt-in nudge for the child who has stalled: spin once, get a random outstanding chore, and earn a multiplier on it if they do it. Off by default. ([#696](https://github.com/tempus2016/taskmate/pull/696))

**New — rewards**
- **Timed unlock rewards** — spend points to unlock something for a while: the TV, the console socket, a wifi group. Approving the claim turns the entity on and a timer turns it back off. Gated by a parent allowlist, so a child can only ever unlock what you have permitted. ([#697](https://github.com/tempus2016/taskmate/pull/697))

**New — cards**
- **Routine mode** — a guided, one-task-at-a-time flow for morning and bedtime. The child card is a checklist, which is good for scanning but poor for walking a five-year-old through getting ready. Routine mode shows a single task with a big **Done** button, a progress bar, and a celebration at the end. ([#695](https://github.com/tempus2016/taskmate/pull/695))
- **Pre-reader mode** — a picture-only child card for children who can't read yet. No chore names, no numbers: a big icon, a row of stars for the points, and a huge tick when it's done. ([#702](https://github.com/tempus2016/taskmate/pull/702))
- **Accessible design style** — a fifth per-card design alongside Classic, Playroom, Console and Clean Pro. High contrast, the Okabe-Ito colour-blind-safe palette, and Atkinson Hyperlegible type. Pick it per card or as the global default. ([#704](https://github.com/tempus2016/taskmate/pull/704))

**New — admin panel**
- **Insights** — four reports answering the questions the raw numbers don't. **Fairness**: am I dumping everything on the eldest? **Friction**: which chores are quietly never getting done? **Week ahead**: what points are actually available in the next seven days? **Health**: is anything misconfigured? ([#698](https://github.com/tempus2016/taskmate/pull/698), [#699](https://github.com/tempus2016/taskmate/pull/699), [#700](https://github.com/tempus2016/taskmate/pull/700), [#701](https://github.com/tempus2016/taskmate/pull/701))

**New — notifications**
- **Evidence photo attached to the approval push** — the photo a child submits as proof now arrives in the notification itself, so you can approve from the lock screen without opening the app. ([#705](https://github.com/tempus2016/taskmate/pull/705))
- **Multi-parent approval routing** — by default every approval buzzes every parent. You can now route approvals to whoever is currently home, or share them round-robin. ([#706](https://github.com/tempus2016/taskmate/pull/706))

**New — everything else**
- **Read aloud** — speak a child's outstanding chores to a media player: *"Ella, you have three things left: make your bed, brush your teeth and pack your bag."* ([#703](https://github.com/tempus2016/taskmate/pull/703))
- **Shareable template packs** — export your custom chore templates as a JSON pack, and import one somebody else made. ([#707](https://github.com/tempus2016/taskmate/pull/707))
- **Printable weekly chart** — a fridge-ready A4 chore chart with a box to tick against every task. ([#708](https://github.com/tempus2016/taskmate/pull/708))
- **Guest child profiles** — a visiting cousin gets a temporary profile that expires on its own and stays out of the family leaderboard. ([#710](https://github.com/tempus2016/taskmate/pull/710))
 
**Fixes**
- **Routine mode now honours the card design setting** — the new routine card shipped without design-system wiring, so it accepted `card_design` and silently ignored it, rendering identically under every style. It now follows the per-card and global design setting like every other card, including the new Accessible style, and has a design picker in its editor. ([#722](https://github.com/tempus2016/taskmate/pull/722), fixes [#721](https://github.com/tempus2016/taskmate/issues/721))
- **Two high-severity dev-dependency advisories resolved** — build tooling only; nothing shipped to Home Assistant was affected. ([#711](https://github.com/tempus2016/taskmate/pull/711))
 
### v4.5.1
 
**Improved**
- **Easier mobile navigation in the admin panel** — on phones, the admin panel no longer packs every section into a single horizontally-scrolling tab strip that you had to swipe across to reach Settings. Instead a **section picker** shows the current section; tap it to open a grouped list (Today / Manage / System) that mirrors the desktop sidebar — with the same count badges and highlight — and jump straight to any section in one tap. Desktop is unchanged. ([#669](https://github.com/tempus2016/taskmate/pull/669))
- **Clickable template packs** — on the **Templates** tab, built-in and custom pack cards are now clickable and open the preview (chore list + **Create N chores**); the chores toolbar button is clearer as **Create from template** (all locales). ([#665](https://github.com/tempus2016/taskmate/pull/665))
 
**Fixes**
- **Mobile styling sweep** — audited every card and the admin panel at phone widths and fixed the overflow, clipping and broken-layout issues found: the Children stat grid now lays out as a clean 2×2 instead of leaving empty cells, the points-card add dialog and toast no longer run off-screen on narrow phones, the Parents (no-admin) rows sit inline, and more. ([#666](https://github.com/tempus2016/taskmate/pull/666), [#665](https://github.com/tempus2016/taskmate/pull/665))
 
### v4.5.0
 
**New**
- **Parent access without admin rights** — you can now give a second parent day-to-day control of TaskMate without making them a Home Assistant admin. In **Settings → Parents (no admin rights)**, tick any existing non-admin Home Assistant user; they can then approve or reject chores, adjust points, confirm rewards and allowance payouts, award badges, complete chores on a child's behalf, and undo — straight from the cards. They still **cannot** open the admin panel or change any configuration, and every parent action is recorded in the audit log. Ideal for a partner who wants to run the daily routine but shouldn't have full Home Assistant admin rights. ([#662](https://github.com/tempus2016/taskmate/pull/662), fixes [#661](https://github.com/tempus2016/taskmate/issues/661))
 
### v4.4.4
 
**New**
- **Undo a bonus sub-task by tapping it again** — a completed bonus sub-task on the Child Card can now be un-completed with a second tap, mirroring the tap-to-undo that top-level chores already had. Reverses only that sub-task's points; the parent chore stays done. Works on the classic and all designed card styles. ([#656](https://github.com/tempus2016/taskmate/pull/656), fixes [#653](https://github.com/tempus2016/taskmate/issues/653))
- **Approval notifications clear from your phone when reviewed** — approving or rejecting a chore (or reward) — including with **Approve All** — now dismisses its push notification from the Home Assistant companion app, so a big approval sweep no longer leaves a pile of stale alerts. Clearing is limited to `mobile_app.*` notify targets, so other channels (Telegram, email, persistent) are never spammed. ([#658](https://github.com/tempus2016/taskmate/pull/658), fixes [#655](https://github.com/tempus2016/taskmate/issues/655))
- **In-page lightbox for chore evidence photos** — tapping a chore evidence photo now opens it in an in-page lightbox instead of jumping to the raw image in a new browser tab. Applies to the Approvals card, Parent Dashboard card, the panel's pending-approvals view, and the Photo Gallery card (classic and designed styles). ([#652](https://github.com/tempus2016/taskmate/pull/652))
 
**Fixes**
- **Badges can be created and edited from the UI again** — saving a badge failed every time with `extra keys not allowed @ data['combinator']`. The badge editor always sends the `combinator` field (AND/OR), but the `add_badge`/`update_badge` service schemas never allowed it. Both schemas now accept it. ([#657](https://github.com/tempus2016/taskmate/pull/657), fixes [#654](https://github.com/tempus2016/taskmate/issues/654))
 
### v4.4.3
 
**New**
- **Approve All on pending approvals** — when several chore completions are waiting for a parent's sign-off, you can now clear the whole queue with a single **Approve All** button instead of approving each one. The button appears on both the TaskMate panel's pending-approvals view and the **Approvals card**, and runs every award, badge, quest and celebration side-effect exactly as approving each chore by hand would. Backed by a new `taskmate.approve_all_chores` service (approves all pending, or a specific list of `completion_ids`) and a matching `taskmate/approve_all_chores` WebSocket command. ([#647](https://github.com/tempus2016/taskmate/pull/647), [#648](https://github.com/tempus2016/taskmate/pull/648))
 
**Changed**
- **Dashboard card-picker suggestions (HA 2026.6+)** — every TaskMate card now implements `getEntitySuggestion`, so Home Assistant's "add card" picker pre-fills a sensible TaskMate entity instead of leaving the card blank when you drop it onto a dashboard. ([#646](https://github.com/tempus2016/taskmate/pull/646))
 
### v4.4.2
 
**Fixes**
- **Rewards Card: depositing points into a pool/jackpot reward no longer crashes** — `allocate_points_to_pool` failed with `'TaskMateCoordinator' object has no attribute 'get_children'` whenever the kiosk cross-child safety check ran (a non-admin/shared-tablet session depositing to an unlinked child). The child roster is now looked up on the correct object, so deposits work again. ([#642](https://github.com/tempus2016/taskmate/pull/642), fixes [#641](https://github.com/tempus2016/taskmate/issues/641))
 
### v4.4.1
 
**Fixes**
- **Photo-proof upload no longer fails on long sessions** — the child card's photo upload sent a manually-cached access token that expires after ~30 min, so an aged session got a `401` shown as the misleading *"Upload failed. Check your connection."* It now refreshes the token when expired and retries once on a `401`. ([#636](https://github.com/tempus2016/taskmate/pull/636))
- **No more `taskmate-panel` "already defined" console error after upgrades** — guarded the panel's `customElements.define()` so a browser briefly holding both the old and new panel module (different `?v=` cache-busters) no longer throws an uncaught error. ([#636](https://github.com/tempus2016/taskmate/pull/636))
- **Config-entity defaults now match the applied bonus** — the `weekend_multiplier` and `perfect_week_bonus` number entities defaulted to `1.0`/`0`, but the bonus logic falls back to `2.0`/`50` when unset, so a fresh install displayed values that didn't match what was actually applied. Defaults aligned. ([#635](https://github.com/tempus2016/taskmate/pull/635))
 
### v4.4.0
 
**New features**
- **Allowance** — convert points into a real-money pocket-money payout at a fixed conversion rate, with a payout ledger and the `taskmate.record_allowance_payout` service. See [Allowance](#allowance-real-money-payouts).
- **Family Goals** — a single shared, family-wide points target with a one-time goal-reached notification and the new **Family Goal Card**. See [Family Goals](#family-goals).
- **Chore Dependencies** — `depends_on` prerequisites that keep a chore locked until its predecessors are completed and approved for the same child today. See [Chore Dependencies](#chore-dependencies).
- **Leaderboard Seasons** — a fresh monthly leaderboard contest with `sort_by: season`, recorded champions, and an automatic reset on the 1st. See [Leaderboard Seasons](#leaderboard-seasons).
- **Quiet Hours** — per-child do-not-disturb windows that suppress a child's notifications. See [Quiet Hours](#quiet-hours).
- **Reminder Escalation** — a nudge → reminder → parent-alert ladder for missed mandatory chores. See [Reminder Escalation](#reminder-escalation).
- **Monthly report** — a 1st-of-the-month parent recap alongside the weekly digest. See [Weekly Digest & Monthly Report](#weekly-digest--monthly-report).
- **To-Do Lists** — a native HA `todo.taskmate_<child>` list per child; ticking an item completes the chore. See [To-Do Lists](#to-do-lists).
- **Configuration Entities** — `number`/`select` entities mirroring key settings for use from the UI and automations. See [Configuration Entities](#configuration-entities).
- **Voice Assistants** — `TaskMateChoresLeft` and `TaskMatePoints` conversation intents. See [Voice Assistants](#voice-assistants).
- **Calendar subscription** — a token-protected ICS feed (`/api/taskmate/calendar.ics`) for external calendar apps. See [Calendar Subscription](#calendar-subscription-ics-feed).
- **Photo Gallery Card** — browse past photo-proof images. See [Photo Proof](#photo-proof).
- **Automation blueprint pack** — ready-made blueprints for common TaskMate events. See [Automation Blueprints](#automation-blueprints).
- **Negative-balance policy** — optional `allow_negative_balance` to let penalties push a balance below zero.
 
**Fixes & polish**
- Card count is now 20; sensors expose new `family_goal`, `season_*`, and `photo_gallery` attributes; the Leaderboard Card gains `career` and `season` sort modes.
 
See [GitHub Releases](https://github.com/tempus2016/taskmate/releases) for the full changelog.
 
---
 
<p align="center">
  <sub>License: MIT · Data stays local in your Home Assistant instance</sub>
</p>
