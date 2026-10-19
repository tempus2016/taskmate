# Vacation Mode

Vacation mode lets you mark date ranges as time off. During a vacation, all chores are paused and streaks are frozen — days inside a vacation never count as missed, so a streak survives a holiday.

![The Children tab](images/panel-children.png)

---

## What a Vacation Does

While today falls inside a vacation period:

- **All chores are paused** — every chore reports as unavailable, so children see nothing to do (the child card shows an on-vacation banner instead of the chore list).
- **Streaks are frozen** — the nightly streak check is skipped entirely on a vacation day. No streak is reset or paused.
- **Missed days are forgiven** — when the streak check next runs, any vacation days between a child's last completion and today are not counted as misses. A genuine, non-vacation day that was missed still breaks the streak as normal.

Away days also surface as multi-day all-day **"Away"** events on each child's [Calendar](Calendar.md).

---

## Three Ways to Mark Time Off

From v4.1.0 a child can be treated as away from any of three stacking sources, OR'd together. The first two are **global** (they apply to every child); the third is **per-child**.

1. **Static vacation periods** (`vacation_periods`) — named date ranges you define by hand. Historical date math: a day counts as away when it falls inside any period.
2. **Calendar-synced vacations** (`vacation_calendar`) — point the setting at a Home Assistant `calendar.*` entity and TaskMate follows it live: whenever that calendar has an active event, every child is treated as away for as long as the event runs. Fail-open — a missing or broken entity never freezes anyone. Leave the setting empty to disable.
3. **Per-child availability** — a child who opts in with `pause_streak_when_unavailable` is treated as away whenever their own availability sensor (which may itself be a `calendar.*` entity) reports them unavailable. This affects only that child.

While a child is away — from any source — their **streak is paused**: no streak break, and no missed-mandatory penalties pile up for those days.

---

## Setting Up a Vacation

Add and remove vacation periods in the [Admin Panel](Admin-Panel.md) under **Settings**, using the vacation editor. Each period has:

| Field | Description |
|-------|-------------|
| **Name** | Optional label (e.g. "Summer holiday") |
| **Start** | First day of the vacation (inclusive) |
| **End** | Last day of the vacation (inclusive) |

Both bounds are inclusive ISO dates. If you enter the end before the start, TaskMate swaps them automatically. Up to 50 periods can be stored.

Periods are saved in the `vacation_periods` setting as a list of `{ id, name, start, end }` entries, sorted by start date.

---

## What Resumes Afterwards

There is nothing to switch back on. The moment the current date moves past a vacation's end date:

- Chores become available again on their normal schedule.
- The nightly streak check runs again. Because the vacation days were forgiven, a child who was on a streak before the holiday keeps it — completing on the first day back continues the run.

---

## Sensor Attributes

Both `sensor.taskmate_overview` and the chores sensor expose the current vacation state:

| Attribute | Description |
|-----------|-------------|
| `vacation_active` | `true` if today is inside any vacation period |
| `vacation_name` | Name of the active period (empty if none) |
| `vacation_end` | End date of the active period (empty if none) |

`sensor.taskmate_overview` additionally exposes `vacation_periods` — the full validated list, for cards or automations that want to show upcoming time off.

---

## Guests Use the Same Mechanism

When a [guest profile](Guest-Child-Profiles.md) reaches its end date it is **archived**, which reuses this same availability path. Every chore, streak and rotation rule already treats an archived guest exactly as it treats a child who is away — there is no second code path that could disagree.

## Related

- [Calendar](Calendar.md) — "Away" events on the per-child calendars
- [Chores](Chores.md) — chore availability
- [Bonus Points](Bonus-Points.md) — streak milestones and perfect-week bonuses that vacations protect
