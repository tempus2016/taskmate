# Chore Roulette

An opt-in nudge for the child who has stalled: spin once, get a random outstanding chore, and earn a multiplier on it if they do it.

![Roulette settings](images/panel-settings.png)

It is a way of turning "I don't know where to start" into one specific thing worth extra.

---

## Turning It On

Roulette is **doubly opt-in** — it needs both a global setting and a card setting, so an existing dashboard never sprouts a new button unasked.

1. **Settings** — enable roulette (off by default), and set the multiplier and how many spins a child gets per day.
2. Add `show_roulette: true` to the child card:

```yaml
type: custom:taskmate-child-card
entity: sensor.taskmate_overview
child_id: <child_id>
show_roulette: true
```

---

## Key Points

- **Roulette only ever picks a chore the child is actually allowed to do right now.** It runs the same availability check as everything else, so the [weather gate](Weather-Aware-Chores.md), [deadlines](Reactive-Chores.md), [dependencies](Chore-Dependencies.md) and rotation are all respected.
- The pick is recorded **per child, per day**. It survives a reload, can't be re-rolled past the daily allowance, and expires overnight.
- **A re-spin moves to a different chore** where one is available, rather than handing back the same one.
- The multiplier is applied **at completion**, and stacks with the [difficulty](Difficulty-Tiers.md) multiplier and any [speed bonus](Reactive-Chores.md).
- **A multiplier below 1 is clamped to 1.** Spinning should never punish the child for trying.
- The spin button renders under **all six** [card design styles](Card-Design-Styles.md), taking its colour from the active design's accent.

---

## Spinning from an Automation

Children spin via the `taskmate.spin_roulette` service, which the card calls for them:

```yaml
action: taskmate.spin_roulette
data:
  child_id: <child_id>
```

Spinning fires `taskmate_roulette_spun`:

| Field | Meaning |
|-------|---------|
| `child_id` / `child_name` | Who spun |
| `chore_id` / `chore_name` | What they landed on |
| `multiplier` | The multiplier that will apply |
| `timestamp` | When |

---

## Related

- [Chores](Chores.md) — what makes a chore available to be picked
- [Difficulty Tiers](Difficulty-Tiers.md) — the other multiplier, which stacks with this one
- [Reactive Chores](Reactive-Chores.md) — speed bonuses, which also stack
- [Services](Services.md) — the full `taskmate.spin_roulette` signature
- [Settings](Settings.md) — the global roulette settings
