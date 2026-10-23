# Bin-Day Chores

The evening before a bin collection, TaskMate reads your bin calendar and adds a chore for each bin going out: *"♻️ Put the Recycling out"*. Optionally a second one appears on collection day: *"♻️ Bring the Recycling in"*.

---

## Setting It Up

You need a calendar in Home Assistant with your collection days on it — [Waste Collection Schedule](https://github.com/mampfes/hacs_waste_collection_schedule), your council's iCal feed through the **Remote calendar** integration, or a local calendar you fill in yourself.

**Settings → Bin-day chores** in the TaskMate panel:

| Setting | What it does |
|---------|--------------|
| **Turn on bin-day chores** | The switch for the whole feature |
| **Bin calendars** | Up to 5 calendars. **Show the next collections** lists the next two weeks so you can check it's reading the right thing (save first) |
| **Put-out time** | When the chore appears the evening before. Default 18:00 |
| **Points per chore** | 0–1000. Default 5 |
| **Who does it** | **First to do it** — every chosen child sees it and the first to finish gets the points. **Take turns** — one child per chore, round the chosen children in order |
| **Children** | None picked means every child who isn't an [adult](Adult-Profiles.md) |
| **Bring the bins back in** | Adds the bring-in chore on collection day |
| **Bring-in time** | When that one appears. Default 16:00 |

---

## How It Works

- **One chore per event.** Each calendar event on tomorrow's date becomes a chore named after it, so a calendar with "Recycling" and "Garden waste" on the same day gives two chores. The same bin on the same day is only ever raised once, however many calendars carry it or however often they're read.
- The calendar is read at the put-out time and again every 15 minutes until midnight, so a collection added late in the evening still gets its chore.
- The chore is a [reactive chore](Reactive-Chores.md): a one-off with a deadline at the end of that evening. It needs approval like any other chore.
- The emoji comes from the event's name: ♻️ for recycling, blue, paper, card, plastic or tins; 🌿 for garden, green, brown, compost or food; 🍾 for glass or bottles; 🗑️ for anything else.
- The words around the bin name follow Home Assistant's language: *"Put the {bin} out"* in English, *"{bin} rausstellen"* in German.

---

## Automations

Each chore fires `taskmate_bin_day`:

| Field | Meaning |
|-------|---------|
| `chore_id`, `chore_name` | The chore that was added |
| `bin` | The calendar event's name |
| `kind` | `put_out` or `bring_in` |
| `child_ids` | Who can do it |
| `timestamp` | When it was added |

It also shows on the family [event entity](Event-Entities.md) as **Bin-day chore**.

```yaml
# Flash the hall light when the bins need to go out
triggers:
  - trigger: event
    event_type: taskmate_bin_day
    event_data:
      kind: put_out
actions:
  - action: light.turn_on
    target:
      entity_id: light.hall
    data:
      flash: short
```

---

## Related

- [Reactive Chores](Reactive-Chores.md) — the one-off-with-a-deadline chore type these use
- [Calendar](Calendar.md)
- [Automations](Automations.md)
