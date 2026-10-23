# Chores at Set Times

*(v7.3.0)* A chore can come up at up to five set times a day: wash hands at breakfast, lunch and dinner, or an inhaler at 8am and 8pm. Each time is ticked off on its own, only while it's open, and earns its own points.

---

## Setting It Up

In the chore editor, under **When**, **How often in a day** has three choices:

| Choice | What it does |
|--------|--------------|
| **Once** | One tick a day (the usual chore) |
| **Up to N times** | Up to the daily limit, at any time of day |
| **At set times** | Each time is its own tick |

Pick **At set times**, then start from a preset or add your own times with **＋ Add a time**:

- 🍽️ Breakfast · lunch · dinner
- 🪥 Morning & evening
- 💊 8am · 2pm · 8pm
- 🐶 Pet: breakfast & tea

Each time has:

| Field | Meaning |
|-------|---------|
| **Name** | Shown to the child, e.g. *Lunch*. Up to 30 characters |
| **From** / **Until** | When the time is open (`HH:MM`) |
| **Points** | What this time pays, 0–1000 |

The strip under the times shows the whole day, so you can see the gaps between them. **All-times bonus** adds extra points once a day, when every time is done (0 = none).

**The rules:**

- At most 5 times.
- A time must close after it opens, on the same day. Times can't overlap or cross midnight.
- A chore with set times can't also be a timed, open-ended, quantity or teamwork chore.

The editor checks all of this as you type, and the services and WebSocket API refuse anything that breaks a rule before saving.

---

## How It Works

- **One tick per time per day.** A child can tick a time while it's open, plus the chore's [claim allowance](Chores.md) (grace minutes after it closes). Before it opens it shows *opens 12:00*; after, *missed*.
- **Parents can tick any time** that isn't done yet, open or not.
- **Approvals, undo and reject work per time.** Everywhere a completion is named (approvals, notifications, the activity feed, the mandatory review) it reads *Wash hands (Lunch)*.
- **For the day as a whole the chore counts once**, and only once every time is done. That's what moves the [streak](Per-Chore-Streaks.md), the [weekly target](Weekly-Targets.md) and the per-week figures on the weekly card. Re-ticking a time that was rejected earns the streak back.
- **[Mandatory chores](Mandatory-Chores.md)** owe a miss for each time that closes without being done.
- **Editing the times mid-day keeps today's ticks.** A time keeps its identity if its name (or, failing that, its start) matches, so you can move *Lunch* from 12:00 to 12:30 without losing a tick already made.

---

## On the Cards

The [child card](Dashboard-Cards.md) and [kiosk](Kiosk-Mode.md) show a chore with set times one of two ways:

| Layout | Looks like |
|--------|------------|
| **One row per time** | *Wash hands · Breakfast*, *Wash hands · Lunch*, … each with its own tick |
| **One row, a pill per time** | One *Wash hands* row with a pill for each time: done, now, later, missed |

Choose the family's layout in **Settings → Chores with set times**. Each child and kiosk card can override it with the `set_times_layout` option:

| Value | Meaning |
|-------|---------|
| `family` | Use the family setting (default) |
| `rows` | One row per time |
| `pills` | One row, a pill per time |

The panel's **Today** chore board shows each time separately, and the Chores list marks these chores *Set times: 3*.

---

## Services

`taskmate.complete_chore` takes an optional `time_id`: the set time to tick off. Leave it out and the time that's open now is ticked.

`taskmate.add_chore` takes:

| Field | Meaning |
|-------|---------|
| `times` | A list of up to 5 times, each `name`, `start`, `end` (`HH:MM`) and `points` |
| `times_bonus` | The all-times bonus, 0–1000 |

```yaml
action: taskmate.add_chore
data:
  name: Wash hands
  points: 0
  times:
    - { name: Breakfast, start: "07:00", end: "09:00", points: 2 }
    - { name: Lunch, start: "12:00", end: "13:30", points: 2 }
    - { name: Dinner, start: "17:00", end: "19:00", points: 2 }
  times_bonus: 5
```

A bad set of times refuses the whole call, so no half-made chore is left behind. To change the times later, edit the chore in the panel.

---

## Related

- [Chores](Chores.md)
- [Chore Scheduling](Chore-Scheduling.md)
- [Mandatory Chores](Mandatory-Chores.md)
- [Services](Services.md)
