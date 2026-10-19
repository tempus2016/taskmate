# Levels and XP

Every point a child has ever earned counts as XP, and XP turns into levels. It is a zero-config progression layer that sits on top of the points they already earn — no extra setup needed to get going.

![A child's level and progress on the Child card](images/card-child.png)

---

## How It Works

A child's **XP is their lifetime earned points** (`total_points_earned`). This is the cumulative total of everything they've ever earned — chore completions, weekend bonuses, streak milestones, perfect weeks, quest and challenge bonuses, badge point bonuses, manual bonuses, and savings interest. Spending points on rewards does **not** reduce XP, so a child's level only ever goes up.

```
Lifetime earned points (XP) → Level → Level-up event + celebration
```

Levels are recalculated automatically every time a child's earned total changes. When the total crosses a level boundary, TaskMate:

1. Updates the child's `level`
2. Fires a `taskmate_level_up` bus event (one per level crossed)
3. Sends the optional `level_up` notification (see [Notifications](Notifications.md))
4. Fires a [celebration](Celebrations.md) — epic at every 5th level, medium otherwise

If a child's earned total ever drops (for example a parent undoes a bonus), the level re-syncs quietly downward with no event.

---

## The Level Curve

Levels use a flat, predictable step: each level costs the same amount of XP.

| Setting | Default | Description |
|---------|---------|-------------|
| **XP per level** (`level_xp_step`) | `100` | Earned points needed to advance one level |

- Level 1 starts at 0 XP
- With the default step of 100, a child reaches level 2 at 100 lifetime points, level 3 at 200, and so on
- The formula is `level = (lifetime earned points ÷ XP per level) + 1`

Set the step lower for faster, more frequent level-ups (good for younger kids) or higher to make levels feel more earned.

Configure it in the Admin Panel's **Settings** tab under **XP per level**.

---

## Where Level & XP Appear

### Overview sensor

Each child in the `sensor.taskmate_overview` `children` attribute carries:

| Field | Description |
|-------|-------------|
| `level` | Current level |
| `level_progress` | XP earned toward the next level (0 up to the step size) |
| `level_target` | XP needed for the next level (the step size) |
| `total_points_earned` | Lifetime earned points — the raw XP value |

`level_progress` resets to 0 each time a child levels up and counts up to `level_target`.

### Child card

The [child card](Dashboard-Cards.md) shows a **level badge** (e.g. "Lvl 4") beside the child's name, with an **XP progress bar** underneath that fills as they close in on the next level. Hovering the badge shows the exact `progress / target` XP. The badge appears automatically once a child has a level.

---

## Levels Power Other Features

- **[Avatars](Avatars.md)** can be unlocked by reaching a level
- **Level-up moments** feed the [celebration](Celebrations.md) system and the `level_up` notification

---

## Automation Example

### Announce a level-up on a speaker

```yaml
alias: Announce level up
triggers:
  - trigger: event
    event_type: taskmate_level_up
actions:
  - action: tts.google_translate_say
    data:
      entity_id: media_player.kitchen_speaker
      message: >
        {{ trigger.event.data.child_name }} reached level
        {{ trigger.event.data.level }}!
```

The `taskmate_level_up` event payload includes `child_id`, `child_name`, `level`, and `timestamp`.

---

## Related

- [Avatars](Avatars.md) — unlock avatars by reaching levels
- [Celebrations](Celebrations.md) — the tiered moments fired on level-up
- [Dashboard Cards](Dashboard-Cards.md) — child card level badge and XP bar
- [Notifications](Notifications.md) — the `level_up` notification type
- [Bonus Points](Bonus-Points.md) — streaks, perfect weeks and other earned points that feed XP
