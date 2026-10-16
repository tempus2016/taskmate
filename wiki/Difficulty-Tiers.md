# Difficulty Tiers

Every chore carries a difficulty tier. The points a chore awards are its base points multiplied by the tier's multiplier, so harder chores can be worth more without re-entering point values by hand.

![Chore difficulty in the Chores tab](images/panel-chores.png)

---

## Tiers and Default Multipliers

| Tier | Default Multiplier | Effect on a 10-point chore |
|------|--------------------|----------------------------|
| `easy` | ×0.5 | 5 points |
| `medium` | ×1.0 | 10 points |
| `hard` | ×2.0 | 20 points |

**Medium is the neutral baseline (×1.0) and is the default.** Chores created before difficulty tiers existed default to medium, so they keep their exact award value — nothing changes unless you set a chore to easy or hard.

The awarded total is rounded to the nearest whole number and never goes below zero.

---

## Setting a Chore's Difficulty

Set difficulty in the **Difficulty** selector in the chore dialog (add and edit) of the [Admin Panel](Admin-Panel.md), or pass `difficulty` to the `taskmate.add_chore` service. Valid values are `easy`, `medium`, `hard`; anything else falls back to medium.

The child card shows the **effective** (post-multiplier) points, so a hard 10-point chore reads as 20.

---

## Difficulty Badge on the Child Card

Since v4.0.1, children also see the difficulty tier directly on each chore as a small badge:

| Tier | Badge |
|------|-------|
| `easy` | **Easy** badge |
| `medium` | no badge (it is the baseline) |
| `hard` | **Hard** badge |

Medium shows no badge, so a chore card stays uncluttered for the common case. Previously the tier was only visible indirectly through the (post-multiplier) points value.

---

## Editing the Multipliers

The per-tier multipliers are configurable in the [Admin Panel](Admin-Panel.md) under **Settings → Difficulty multipliers**. There are three inputs:

| Setting | Default | Range |
|---------|---------|-------|
| `difficulty_multiplier_easy` | 0.5 | 0.0–10.0 |
| `difficulty_multiplier_medium` | 1.0 | 0.0–10.0 |
| `difficulty_multiplier_hard` | 2.0 | 0.0–10.0 |

Changing a multiplier affects all chores at that tier going forward. Multipliers are global, not per-chore.

> **Note:** Keeping medium at ×1.0 is recommended — it is the baseline that preserves existing chore values. You can change it, but every medium chore (including legacy ones) will then be rescaled.

---

## Interaction with Other Features

- **Base points** are what you enter on the chore; the multiplier scales them at award time on both completion and approval.
- **Early bonus / late penalty** (see [Chores](Chores.md)) are applied *after* the difficulty multiplier — the tier scales the base, then the time adjustment is added or subtracted.
- **Timed chores** earn by rate window, not base points, so the difficulty multiplier does not apply to them.

---

## Sensor Attributes

Each chore in `sensor.taskmate_overview` → `chores` emits difficulty fields only when they are non-default, to keep the payload compact:

| Attribute | When emitted | Description |
|-----------|--------------|-------------|
| `difficulty` | Only when not `medium` | The chore's tier (`easy` / `hard`) |
| `effective_points` | Only when it differs from base `points` | The post-multiplier award value |

A plain medium chore emits neither field, so cards can assume base points unless `effective_points` is present.

The chore completion event (`taskmate_chore_completed`) reports the effective `points` plus a `difficulty` field.

---

## Related

- [Chores](Chores.md) — chore configuration and the difficulty field
- [Admin Panel](Admin-Panel.md) — where the selector and multiplier inputs live
