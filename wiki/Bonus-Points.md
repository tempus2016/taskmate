# Bonus Points

TaskMate has three bonus point systems on top of regular chore completion. All are configured in the **TaskMate** panel → **Settings**.

![Bonus settings](images/panel-settings.png)

> **See also:** From v4.0.0 TaskMate also runs a set of **automatic point mechanics** — a random daily **surprise bonus**, periodic **savings interest**, and optional **points decay**. These award (or remove) points independently of chores and are documented on the [Points Economy](Points-Economy.md) page. The surprise bonus is the automatic cousin of the manual bonuses described here.

---

## Weekend Points Multiplier

Children earn extra points for completing chores on Saturdays and Sundays.

| Setting | Default | Range |
|---------|---------|-------|
| Weekend Points Multiplier | `2.0` | `1.0` – `5.0` |

**How it works:**
- The multiplier applies to the base points of the chore
- A 10-point chore on Saturday with a 2.0× multiplier earns 10 + 10 = **20 points**
- The base points and bonus points are logged as **separate transactions** in the activity feed
- The multiplier is based on the **completion date**, not the approval date — fair for weekend chores approved on Monday

**Set to `1.0` to disable.**

---

## Streak Milestone Bonuses

Children earn bonus points when they hit streak milestones.

| Setting | Default |
|---------|---------|
| Streak Milestone Bonuses | `on` |
| Streak Milestone Configuration | `3:5, 7:10, 14:20, 30:50, 60:100, 100:200` |

### Default Milestones

| Streak | Bonus |
|--------|-------|
| 3 days | +5 points |
| 7 days | +10 points |
| 14 days | +20 points |
| 30 days | +50 points |
| 60 days | +100 points |
| 100 days | +200 points |

### Custom Milestones

Enter your own milestones as `days:points` pairs, comma-separated:

```
3:5, 7:10, 14:20, 30:50, 60:100, 100:200
```

**Rules:**
- Day counts must be positive integers
- Points must be positive integers
- Pairs must be separated by commas
- Invalid format shows a validation error on save and falls back to the default list
- Leave the field empty to disable all milestones without turning off the toggle

**Examples:**

More frequent, smaller bonuses for younger kids:
```
1:2, 3:5, 5:8, 7:15, 14:30, 30:75
```

Fewer, bigger milestones:
```
7:15, 30:75, 100:250
```

### Milestone Behaviour

- Milestones are **re-earnable** — if a streak resets to 0, children can earn the same milestones again
- The `streak_milestones_achieved` list is cleared when a streak resets, so children start fresh
- Each milestone is only awarded once per streak cycle — a child won't earn the 7-day bonus twice in the same streak
- The bonus is logged in the activity feed as a streak milestone event

---

## Perfect Week Bonus

Children earn a bonus when they complete at least one chore every day Monday–Sunday.

| Setting | Default | Range |
|---------|---------|-------|
| Perfect Week Bonus | `on` | — |
| Perfect Week Bonus Points | `50` | `0` – `1000` |
| Perfect week needs all tasks (`perfect_week_requires_all_chores`) | `off` | on / off |

**How it works:**
- Checked every night as part of TaskMate's midnight maintenance, looking at **last week** (Monday–Sunday). A week whose last approval lands on Tuesday is paid on Tuesday night.
- Requires at least one **approved** chore completion on each of the 7 days (Mon–Sun) — or, with **Perfect week needs all tasks** enabled, *every* chore due that day must be done before the day counts. Completions still waiting for approval don't count until they're approved.
- Each week is awarded once per child — duplicates are prevented even if the check runs twice
- If a completion from a paid week is later rejected or un-approved and the week no longer qualifies, the bonus is taken back ("Perfect week bonus reversed"). Re-approving the day lets the nightly check pay it again.
- The awarded weeks are stored as a list of Monday ISO dates on the child record
- The bonus is logged in the activity feed

---

## Streak Tracking

### How Streaks Work

- A streak increments when a child completes at least one chore on a given day
- With **Streak needs all tasks** (`streak_requires_all_chores`) enabled, the day only counts once *every* chore due that day is done
- Streaks are checked every night at **midnight** by the coordinator scheduler
- The check compares `last_completion_date` against today's date

### Streak Reset Mode

| Mode | Behaviour |
|------|-----------|
| `reset` (default) | Missing a day resets the streak to 0 |
| `pause` | Missing a day pauses the streak — it resumes from where it left off on the next completion |

**Pause mode** is useful for holidays, sick days, or families that want to be less strict. The `streak_paused` flag is set on the child record when a day is missed in pause mode.

### Best Streak

`best_streak` is the highest `current_streak` value the child has ever had. It never decreases and is used in the Leaderboard card's streak ranking.

---

## Settings Reference

All bonus settings in one place:

| Setting | Default | Description |
|---------|---------|-------------|
| Weekend Points Multiplier | `2.0` | Multiplier on Sat/Sun — set `1.0` to disable |
| Streak Milestone Bonuses | `on` | Master toggle for all milestone bonuses |
| Streak Milestone Configuration | `3:5, 7:10, 14:20, 30:50, 60:100, 100:200` | Custom `days:points` pairs |
| Streak needs all tasks | `off` | Only extend a streak once every chore due that day is done |
| Perfect Week Bonus | `on` | Toggle perfect week bonus |
| Perfect Week Bonus Points | `50` | Points awarded per perfect week |
| Perfect week needs all tasks | `off` | A day counts only when every chore due that day is done |
| Streak Reset Mode | `reset` | `reset` or `pause` |
| History Days to Keep | `90` | Completion history retention: 30–365 days |
| Notification Service | *(empty)* | HA notify service for approval alerts e.g. `notify.mobile_app_your_phone` |
