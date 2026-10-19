# Reactive Chores

A reactive chore is one raised by an automation that must be done *now*: *"the washing machine finished — empty it within 30 minutes."* It carries a deadline, an optional speed bonus, and it disappears when the moment has passed.

![The Chores tab](images/panel-chores.png)

These are created from automations rather than the panel, because the whole point is that something in the house triggered them.

---

## Creating One

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
|-------|--------|
| `expires_in_minutes` | Deadline this many minutes from now. `0` means no deadline — an ordinary chore. Maximum 10080 (one week). |
| `speed_bonus_points` | Extra points awarded if the chore is completed before the deadline. |

---

## How It Works

- **A chore with a deadline is automatically one-shot.** It exists to be done now and never carries into tomorrow.
- The child card shows a live **countdown badge** — amber, turning red under five minutes — with the speed bonus displayed alongside it.
- **Beat the deadline** and `speed_bonus_points` is added on top of the normal award. This *stacks* with the early-bonus / late-penalty of `due_time` if the chore has one, and with the [Chore Roulette](Chore-Roulette.md) multiplier.
- **Miss it** and the chore disappears and is soft-disabled. The sweep runs on the 30-second poll, so a 30-minute chore doesn't sit on the card until midnight looking live.

---

## Reacting to a Miss

Expiry fires a `taskmate_chore_expired` event so an automation can nag, re-raise the chore, or just log it:

| Field | Meaning |
|-------|---------|
| `chore_id` | The chore that expired |
| `chore_name` | Its name |
| `deadline_at` | When it was due |
| `timestamp` | When the expiry was processed |

```yaml
triggers:
  - trigger: event
    event_type: taskmate_chore_expired
actions:
  - action: notify.mobile_app_phone
    data:
      message: "{{ trigger.event.data.chore_name }} wasn't done in time."
```

---

## Related

- [Chores](Chores.md) — the full list of chore fields
- [Chore Roulette](Chore-Roulette.md) — the multiplier that stacks with a speed bonus
- [Automations](Automations.md) — every TaskMate bus event, and the blueprint pack
- [Services](Services.md) — the full `taskmate.add_chore` signature
- [Routine Mode](Routine-Mode.md) — honours reactive deadlines automatically
