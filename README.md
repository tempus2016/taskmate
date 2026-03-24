<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/logo.svg" alt="TaskMate" width="180">
</p>
 
<h1 align="center">TaskMate</h1>
 
<p align="center">
  <strong>Turn chores into a game your kids actually want to play.</strong><br>
  A Home Assistant integration for family chore management, smart rewards, and streak tracking.
</p>
 
<p align="center">
  <a href="https://github.com/tempus2016/taskmate/releases"><img src="https://img.shields.io/github/v/release/tempus2016/taskmate" alt="Latest Release"></a>
  <a href="https://github.com/tempus2016/taskmate/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2025.1+-blue" alt="HA Version">
</p>
 
> Originally created by [vinnybad/choremander](https://github.com/vinnybad/choremander). This fork adds 13 Lovelace cards, a bonus points system, streak tracking, reward approval flow, and much more.
 
---
 
## Contents
 
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Setup](#setup)
- [Chores & Rewards](#chores--rewards)
- [Chore Scheduling](#chore-scheduling)
- [Bonus Points System](#bonus-points-system)
- [Penalties](#penalties)
- [Dashboard Cards](#dashboard-cards)
- [Services](#services)
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
 
TaskMate is not yet in the HACS default store. Add it as a custom repository:
 
1. Open **HACS** → Integrations → ⋮ menu → **Custom repositories**
2. Add `https://github.com/tempus2016/taskmate` — category: **Integration**
3. Search "TaskMate" and click **Download**
4. **Restart Home Assistant**
 
### Manual
 
1. Download the [latest release](https://github.com/tempus2016/taskmate/releases/latest)
2. Copy the `taskmate` folder to `/config/custom_components/taskmate/`
3. **Restart Home Assistant**
 
---
 
## Setup
 
### Add the Integration
 
1. **Settings** → Devices & Services → **Add Integration** → search "TaskMate"
2. Choose your points currency name (Stars, Coins, Points, Bucks — whatever motivates your kids)
 
### Configure
 
Click **Configure** on the TaskMate integration card to access:
 
- **Manage Children** — add children, set avatars
- **Manage Chores** — create and edit chores
- **Manage Rewards** — create rewards with a fixed point cost
- **Settings** — bonus points, streak mode, history retention
 
<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/settingsPage.png" alt="Settings Menu" width="500">
</p>
 
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
 
### Reward Types
 
| Type | How to Set | Description |
|------|-----------|-------------|
| **Standard** | Set `Points Cost` | Fixed cost set by the parent |
| **Jackpot** | Enable "Jackpot" toggle | All assigned children's points pool together toward one shared reward |
 
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
 
## Bonus Points System
 
All bonus settings live in **Settings → Integrations → TaskMate → Configure → Settings**.
 
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
2. If a **Notification Service** is configured in Settings, a push notification is also sent
 
### Configuring Push Notifications
 
Go to **Settings → Integrations → TaskMate → Configure → Settings → Notification Service** and enter your notify service:
 
```
notify.mobile_app_your_phone
```
 
Leave empty to use persistent notifications only.
 
> **Tip:** Use `binary_sensor.taskmate_has_pending_approvals` in your own automations for more customised notification logic — see [Automations](#automations--examples).
 
---
 
## Penalties

Deduct points from a child for unwanted behaviour — the flip side of the reward system.

### How It Works

1. Create named penalties (e.g. "Not going to bed = 10 points") via the **Penalties Card** or the `taskmate.add_penalty` service
2. Open the Penalties Card, select the child, and tap **Apply** on the relevant penalty
3. Points are deducted immediately and logged in the activity feed as `Penalty: <name>`

### Penalties Card

```yaml
type: custom:taskmate-penalties-card
entity: sensor.taskmate_overview
title: Penalties          # optional
```

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

## Dashboard Cards
 
> **Header colours:** Every card has a configurable `header_color` option in the visual editor, with its own vibrant default. Change it to match your dashboard theme or differentiate kid vs parent cards.
 
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
 
---
 
### Child Card
 
Kid-friendly chore completion. The entire row is tappable — no small targets. Supports colourful animated badges, confetti celebrations, and completion sounds. Tapping a completed chore undoes it.
 
<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/childCard.png" alt="Child Card" width="300">
</p>
 
```yaml
type: custom:taskmate-child-card
entity: sensor.taskmate_overview
child_id: a8c8376a            # required — see Finding IDs
time_category: anytime        # morning | afternoon | evening | night | anytime | all
due_days_mode: hide           # hide | dim | show — chores not scheduled today
show_countdown: true          # show midnight reset countdown
show_description: false       # show chore description below name
default_sound: coin           # default completion sound
undo_sound: undo              # sound when undoing
header_color: "#9b59b6"
```
 
---
 
### Rewards Card
 
Shows all available rewards with progress bars and claim buttons. After claiming, the button shows "Awaiting parent approval" until approved. Jackpot rewards show a colour-coded contribution bar per child.
 
<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/rewardCard.png" alt="Rewards Card" width="500">
</p>
 
```yaml
type: custom:taskmate-rewards-card
entity: sensor.taskmate_overview
child_id: a8c8376a            # optional — filter to one child
show_child_badges: true       # show which children are assigned each reward
header_color: "#e67e22"
```
 
---
 
### Approvals Card
 
Review and approve or reject chore completions requiring parent sign-off. Items are grouped by date and time of day.
 
<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/pendingApproval.png" alt="Pending Approvals" width="500">
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
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/managePoints.png" alt="Manage Points" width="500">
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
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/reorderCard.png" alt="Reorder Card" width="500">
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
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/parent-dashboard.png" alt="Parent Dashboard" width="500">
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
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/overview.png" alt="Overview" width="500">
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
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/activity.png" alt="Activity" width="500">
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
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/streak.png" alt="Streak" width="500">
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
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/weeklyCard.png" alt="Weekly Card" width="500">
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
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/pointsGraph.png" alt="Points Graph" width="500">
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
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/rewardProgressCard.png" alt="Reward Progress" width="500">
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
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/leaderboardCard.png" alt="Leaderboard" width="500">
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

```yaml
type: custom:taskmate-penalties-card
entity: sensor.taskmate_overview
title: Penalties
header_color: "#e74c3c"
```

---

## Services
 
TaskMate exposes services you can call from automations, scripts, or Developer Tools.
 
| Service | Parameters | Description |
|---------|-----------|-------------|
| `taskmate.complete_chore` | `chore_id`, `child_id` | Mark a chore as completed |
| `taskmate.approve_chore` | `completion_id` | Approve a pending chore completion |
| `taskmate.reject_chore` | `completion_id` | Reject a pending chore completion |
| `taskmate.claim_reward` | `reward_id`, `child_id` | Create a pending reward claim |
| `taskmate.approve_reward` | `claim_id` | Approve a reward claim (deducts points) |
| `taskmate.reject_reward` | `claim_id` | Reject a reward claim |
| `taskmate.add_points` | `child_id`, `points`, `reason` | Manually add points to a child |
| `taskmate.remove_points` | `child_id`, `points`, `reason` | Manually remove points from a child |
| `taskmate.set_chore_order` | `child_id`, `chore_order` | Set the chore display order for a child |
| `taskmate.add_penalty` | `name`, `points`, `description`\*, `icon`\* | Create a new penalty definition |
| `taskmate.update_penalty` | `penalty_id`, `name`\*, `points`\*, `description`\*, `icon`\* | Update an existing penalty |
| `taskmate.remove_penalty` | `penalty_id` | Delete a penalty definition |
| `taskmate.apply_penalty` | `penalty_id`, `child_id` | Apply a penalty — deducts points immediately |

\* optional
 
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
 
Enable **Jackpot** mode on a reward for big family goals — all assigned children's points pool together toward a single shared cost. The rewards card shows each child's contribution as a colour-coded bar segment.
 
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
 
Several card options require a `child_id` or `reward_id`. The easiest way to find these:
 
1. Go to **Developer Tools** → **States**
2. Find `sensor.taskmate_overview`
3. Click the entity to expand its attributes
4. Look in the `children` array for `id` values, or the `rewards` array for reward IDs
 
Alternatively, IDs are visible in the URL when editing a child or reward in the TaskMate configuration UI.
 
---
 
## Troubleshooting
 
**Cards show "Custom element doesn't exist"**
- Hard refresh the browser (Cmd+Shift+R / Ctrl+Shift+R)
- Check Settings → Dashboards → Resources — the `/taskmate/*.js` resources should be listed
- If resources are missing, restart Home Assistant — they are registered automatically on startup
 
**Cards show "Entity not found"**
- Make sure you're using `sensor.taskmate_overview` as the entity (not `sensor.pending_approvals`)
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
- Update to v1.1.6 or later — a fix in v1.1.6 resolves a deeper root cause where resources were being wiped on startup by Lovelace's own storage load
 
---
 
## Tips
 
- **Two dashboards** — One for kids (Child Card + Rewards Card), one for parents (Parent Dashboard). Kids don't need to see the approval queue
- **Completion %** — Set this lower for optional or weekly chores. If a chore is done twice a week, set it to ~30%. This prevents infrequent chores from inflating reward costs
- **Due Days** — Use these so Monday's homework doesn't appear on Saturday. Set `due_days_mode: hide` on the child card
- **Chore descriptions** — Add short instructions like "Put the lid back on the bin" and enable `show_description: true` in the card editor
- **Streak mode: Pause** — If you go on holiday, "Pause" mode means kids don't lose their streak. "Reset" mode is stricter and more motivating for consistent households
- **Weekend Multiplier** — Great for incentivising chores on days kids have more free time. Set it to `1.5` for a gentler boost or `3.0` for a big incentive
- **Jackpot rewards** — Use these for big shared goals. A family holiday, a trip to a theme park, a new board game — something everyone works toward together
- **Header colours** — Each card has its own default colour. Customise them in the visual editor to make the kids' dashboard bright and fun, and the parent dashboard more neutral
- **Per-chore sounds** — Set `completion_sound: fanfare` on harder chores to make completing them feel more rewarding than easy ones
 
---
 
## Changelog
 
See [GitHub Releases](https://github.com/tempus2016/taskmate/releases) for the full changelog.
 
---
 
<p align="center">
  <sub>License: MIT · Data stays local in your Home Assistant instance</sub>
</p>
