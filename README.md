<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/logo.svg" alt="TaskMate" width="180">
</p>

<h1 align="center">TaskMate</h1>
<p align="center">
  <strong>Turn chores into a game your kids actually want to play.</strong><br>
  A Home Assistant integration for family chore management with smart rewards.
</p>

---

## Contents

- [Why TaskMate?](#why-taskmate)
- [Quick Start](#quick-start)
- [Features](#features)
- [Dashboard Cards](#dashboard-cards)
- [Smart Reward Pricing](#smart-reward-pricing)
- [Tips](#tips)
- [Development](#development)

---

## Why TaskMate?

Kids don't naturally love chores. But they *do* love games, progress bars, and earning things. TaskMate turns daily responsibilities into a reward system that actually motivates.

### Build Better Habits Through Gamification

- **Visual progress** toward goals keeps kids engaged
- **Immediate feedback** (points, sounds, celebrations) reinforces positive behavior
- **Clear expectations** - kids know exactly what's required and what they'll earn

### Encourage the Right Behaviors

Not all chores are equal. Some are easy (brush teeth), others take effort (homework, practice). With TaskMate:

- **Weight points by difficulty** - Give 1 star for easy tasks, 5 stars for harder ones
- **Harder chores = faster rewards** - Kids learn that putting in effort pays off
- **No gaming the system** - Smart pricing means you can't just spam easy chores to win

### Flexible Rewards That Make Sense

- **Per-child or shared** - Define rewards for one kid or assign to multiple
- **Smart pricing per child** - Even shared rewards calculate costs individually based on each child's chores and completion rates
- **Control the pace** - Set how many days a reward should take to earn; the system calculates the rest
- **Jackpot rewards** - Pool stars from all kids toward big family goals (vacation, museum trip, etc.)

<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/rewardsCard.png" alt="Rewards Card" width="350">
</p>

---

## Quick Start

### Install via HACS

1. **HACS** → Integrations → ⋮ menu → **Custom repositories**
2. Add `https://github.com/tempus2016/taskmate` as an **Integration**
3. Search "TaskMate" and install
4. **Restart Home Assistant**

### Configure

1. **Settings** → Devices & Services → **Add Integration** → "TaskMate"
2. Choose your points currency (Stars, Coins, Bucks, etc.)
3. Click **Configure** on the integration to manage everything:

<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/settings.png" alt="Settings Menu" width="500">
</p>

---

## Features

### Chores

<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/editChore.png" alt="Edit Chore" width="500">
</p>

| Feature | Description |
|---------|-------------|
| **Points** | Stars earned for completion |
| **Time of Day** | Morning, Afternoon, Evening, Night, or Anytime |
| **Completion % Per Month** | Expected completion rate (100 = daily, 50 = every other day) - used for smart reward pricing |
| **Daily Limit** | How many times per day the chore can be completed |
| **Requires Approval** | Parent must approve before points are awarded |

### Rewards

| Type | Description |
|------|-------------|
| **Dynamic** *(default)* | Cost auto-calculated: `Days to Goal` × expected daily earnings (based on each chore's points and completion rate) |
| **Fixed** | Toggle "Override Point Value" to set a manual cost |
| **Jackpot** | Pool stars from ALL assigned children toward one big family reward |

---

## Dashboard Cards

Cards auto-register when the integration loads. Just add them to your Lovelace dashboard - no manual resource configuration needed!

### Adding Cards (Visual Editor)

The easiest way to add TaskMate cards:

1. Edit your dashboard and click **Add Card**
2. Search for the card (e.g., "taskmate-child-card") or scroll to find it under "Custom"
3. Alternatively, add a **Manual** card and enter the card type (e.g., `custom:taskmate-child-card`)
4. The card will show a configuration interface - enter `sensor.taskmate_overview` in the entity field
5. Fill in any additional options (child selection, time of day, etc.) and save

> **Tip:** If the card shows an error after adding, click on it to open the configuration panel. This is normal - it just needs to be configured!

### YAML Mode Users

If you use Lovelace in YAML mode, add these resources to your `configuration.yaml`:

```yaml
lovelace:
  resources:
    - url: /taskmate/taskmate-child-card.js
      type: module
    - url: /taskmate/taskmate-rewards-card.js
      type: module
    - url: /taskmate/taskmate-approvals-card.js
      type: module
    - url: /taskmate/taskmate-points-card.js
      type: module
    - url: /taskmate/taskmate-reorder-card.js
      type: module
```

### Card Index

| Card | For | Description |
|------|-----|-------------|
| [Child Card](#child-card) | Kids | Kid-friendly chore completion interface |
| [Rewards Card](#rewards-card) | Kids | View available rewards and progress |
| [Approvals Card](#approvals-card) | Parents | Approve or reject completed chores |
| [Points Card](#points-card) | Parents | Manually add/remove points |
| [Reorder Card](#reorder-card) | Parents | Organize chore display order per child |
| [Parent Dashboard](#parent-dashboard-card) | Parents | Unified approvals, overview, claims, and quick points |
| [Overview Card](#overview-card) | Parents | At-a-glance all children progress |
| [Approvals Card](#approvals-card) | Parents | Approve/reject chores and reward claims |
| [Activity Card](#activity-card) | Parents | Full activity history feed |
| [Streak Card](#streak-card) | Kids/Parents | Streak tracking with achievements |
| [Weekly Card](#weekly-card) | Parents | Week view with bar chart |
| [Points Graph Card](#points-graph-card) | Parents | Line graph of points over time |
| [Reward Progress Card](#reward-progress-card) | Kids | Full-screen motivational reward display |
| [Leaderboard Card](#leaderboard-card) | Kids/Parents | Competitive ranking by points, streak, or weekly |

> **Tip:** Create separate dashboards - one for kids (Child + Rewards) and one for parents (Approvals + Points).

---


## Child Card

Kid-friendly interface with big colorful buttons and celebration sounds. This is the primary way children interact with their chores.

<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/kidCard.png" alt="Kid Card" width="300">
</p>

**Visual Editor:** Add `custom:taskmate-child-card`, then configure the entity (`sensor.taskmate_overview`), select a child, and optionally filter by time of day.


<summary>YAML Example</summary>

```yaml
type: custom:taskmate-child-card
entity: sensor.taskmate_overview
child_id: a8c8376a
time_category: morning  # Optional: morning, afternoon, evening, night, anytime
title: My Chores        # Optional
```


## Rewards Card

Shows all available rewards with progress bars. Displays dynamic pricing indicators and jackpot status.

**Visual Editor:** Add `custom:taskmate-rewards-card`, configure the entity, and optionally filter to a specific child.


<summary>YAML Example</summary>

```yaml
type: custom:taskmate-rewards-card
entity: sensor.taskmate_overview
child_id: 6ddfca70  # Optional: filter to specific child
```


## Approvals Card

Review and approve (or reject) completed chores that require parent approval. Shows pending items grouped by time of day.

<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/pendingApprovals.png" alt="Pending Approvals" width="500">
</p>

**Visual Editor:** Add `custom:taskmate-approvals-card` and configure the entity.


<summary>YAML Example</summary>

```yaml
type: custom:taskmate-approvals-card
entity: sensor.pending_approvals
```


## Points Card

Manually add bonus points (great job today!) or remove points (consequences). Useful for situations outside the normal chore flow.

**Visual Editor:** Add `custom:taskmate-points-card` and configure the entity.


<summary>YAML Example</summary>

```yaml
type: custom:taskmate-points-card
entity: sensor.taskmate_overview
```


## Reorder Card

Drag-and-drop interface to organize the order chores appear for each child. Customize the experience per kid.

**Visual Editor:** Add `custom:taskmate-reorder-card`, configure the entity, and select a child.


<summary>YAML Example</summary>

```yaml
type: custom:taskmate-reorder-card
entity: sensor.taskmate_overview
child_id: a8c8376a
```


---

> **Note:** All cards require the `sensor.taskmate_overview` entity. Child-specific cards also need a child selection.


## Parent Dashboard Card
Unified parent control centre with four tabs — Overview (all children's today progress), Approvals (inline approve/reject chore completions), Claims (approve/reject reward claims), and Points (quick +/- buttons per child).
Visual Editor: Add custom:taskmate-parent-dashboard-card and configure the entity.

<p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/parent-dashboard.png" alt="Parent Dashboard" width="500">
</p>

<summary>YAML Example</summary>

```yaml
type: custom:taskmate-parent-dashboard-card
entity: sensor.taskmate_overview
title: Parent Dashboard       # Optional
quick_points_amount: 5        # Optional: points added/removed per button press
show_claims: true             # Optional: show the Claims tab
```

##  Overview Card
At-a-glance summary of all children showing today's chore progress bars, current points, and a pulsing pending approvals badge.
Visual Editor: Add custom:taskmate-overview-card and configure the entity.

 <p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/overview.png" alt="Overview" width="500">
</p>

<summary>YAML Example</summary>
  
```yaml
type: custom:taskmate-overview-card
entity: sensor.taskmate_overview
```

##  Activity Card
Scrollable timeline of all activity including chore completions, manual point adjustments, and reward claim events. Groups by Today / Yesterday / date.
Visual Editor: Add custom:taskmate-activity-card and configure the entity.

 <p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/activity.png" alt="Activity" width="500">
</p>

<summary>YAML Example</summary>

```yaml
type: custom:taskmate-activity-card
entity: sensor.taskmate_overview
child_id: a8c8376a   # Optional: filter to specific child
max_items: 30        # Optional: number of items to show
```

## Streak Card
Per-child streak display with dot history, current and best streak, and achievement badges for hitting milestones (3, 7, 14, 30 days and more).
Visual Editor: Add custom:taskmate-streak-card and configure the entity.

 <p align="center">
  <img src="https://github.com/tempus2016/taskmate/blob/main/images/streak.png" alt="Streak" width="500">
</p>

<summary>YAML Example</summary>

```yaml
type: custom:taskmate-streak-card
entity: sensor.taskmate_overview
child_id: a8c8376a   # Optional: filter to specific child
```


## Smart Reward Pricing

The goal: **every reward should take a predictable amount of time to earn** - not random guessing.

### The Problem with Fixed Prices

If you set "Family Movie Night" to cost 500 stars, how long does that take? A week? A month? You'd have to manually calculate based on all assigned chores... and recalculate every time you add or change one.

### How Smart Pricing Works

You set **Days to Goal** (e.g., 14 days). TaskMate does the math:

1. Looks at each chore's **point value** and **expected completion rate**
2. Calculates how many points the child *should* earn per day
3. Sets the reward cost so it takes exactly that many days

```
Daily Expected Points = Sum of (Chore Points × Completion %)
Reward Cost = Daily Expected Points × Days to Goal
```

### Why This Encourages Better Behavior

Here's the key insight: **completion rate matters**.

If a child only does "Homework" 60% of the time but "Brush teeth" 100% of the time, the pricing reflects that. Kids who consistently do the *harder* chores will hit their goals faster than kids who only do the easy ones.

**The incentive:** Want that reward sooner? Do the challenging stuff, not just the minimum.

| Behavior | Result |
|----------|--------|
| Only does easy daily chores | Earns rewards at the expected pace |
| Tackles harder/optional chores | Earns rewards *faster* than expected |
| Skips difficult chores | Falls behind the expected pace |

### Jackpot Rewards

For big family goals (vacation, museum trip), enable **Jackpot** mode. All children's stars pool together toward one shared reward - teamwork!

---

## Tips

- **Two dashboards:** One for kids (Child + Rewards), one for parents (Approvals + Points)
- **Completion %:** Set lower for optional/weekly chores so they don't inflate reward costs
- **All data is local:** Nothing leaves your Home Assistant instance


<p align="center">
  <sub>License: MIT</sub>
</p>
