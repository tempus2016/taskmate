# Screen-Time Bank

Turn points into minutes of screen time. A reward can buy, say, 30 minutes; approving it puts those minutes in the child's screen-time balance. A free [daily allowance](#daily-allowance) can come on top, and children can [save minutes](#weekend-jar) for the weekend. While the child's devices are on — the TV, a console's smart plug, a tablet's media player — the balance counts down a minute at a time.

---

## Setting It Up

1. **Settings → Screen-time bank** in the TaskMate panel. Switch on **Turn on the screen-time bank**.
2. For each child, **add a device**: a `switch`, `media_player`, `input_boolean`, `binary_sensor`, `remote` or `light`. Up to 10 per child.
3. **Rewards → Add reward**, and fill in **Screen-time minutes** (1–1440). The field appears once the bank is on.

| Setting | What it does |
|---------|--------------|
| **Warn when this many minutes are left** | The *Screen time running low* notification and event fire once when the balance drops to this. `0` turns it off. Default 10 |
| **Turn devices off at zero** | When the balance runs out, TaskMate turns the child's devices off, and turns them off again if they come back on before the balance is topped up |

Each child's row shows their balance (and **on now** while a device is running) with **−15 / +15 / +30** buttons for a quick top-up.

---

## Daily Allowance

Free minutes each day, on top of anything rewards buy. Both default to `0` (no allowance).

| Setting | What it does |
|---------|--------------|
| **Free minutes on school days** | Added at the start of every Monday–Friday that isn't a holiday |
| **Free minutes at weekends and holidays** | Added at the start of Saturdays, Sundays and holidays |
| **Unused allowance** | **Expires at the end of the day** (default) or **Carries over** |

**What counts as a holiday:** a day inside one of the family's [vacation periods](Vacation-Mode.md), or a day the family vacation calendar has an event on when the day starts. A child's own availability sensor and sick days don't change the amount.

**Two buckets.** The balance a child sees is today's allowance plus their *bank*: minutes bought with rewards, parent top-ups, an opened jar, and (with **Carries over**) yesterday's leftover allowance. Watching, and a parent taking minutes away, spends today's allowance first. Banked minutes always carry over; only the allowance can expire.

The allowance is handed out by the first minutely check after midnight. Changing an amount takes effect from the next day. Adults get no allowance. Balances from before the allowance existed are treated as banked.

The card strip adds *"20 min of it is today's allowance"*, and the panel shows the same next to each child's balance.

---

## Weekend Jar

Children can put minutes away for later. With **Weekend jar** switched on:

| Setting | What it does |
|---------|--------------|
| **Jar holds up to (minutes)** | The cap. Default 120 |
| **Jar opens** | Day and time the jar empties into the balance each week. Default Saturday 08:00 |

On the card strip the child taps **Save** and picks 10 or 30 minutes, or **All** of what fits. Below it the jar fills up: *"Weekend jar: 70 / 120 min · opens Saturday 08:00"*.

**What can be saved:** anything in the balance. Today's allowance goes in first (it is the part that would expire), then banked minutes. Saved minutes are locked away until the jar opens.

**When it opens:** at the opening time, every jar that was started before it empties into the child's bank. Minutes saved *after* this week's opening wait for next week's. If Home Assistant was off at the opening time, the jar opens at the next minutely check.

A parent can open a jar early from the child's row in Settings (**Open jar now**), or save on a child's behalf over the `taskmate/screen_time/jar` WebSocket command.

---

## How It Counts

- A device counts as **on** when its state is `on`, `playing`, `paused` or `buffering`. Paused telly is still screen time; `idle`, `standby` and `off` are not.
- **One minute per minute**, however many of the child's devices are on at once.
- The balance never goes below zero, and tops out at a week (10080 minutes).
- A screen-time reward is the child's own: it can't be a jackpot, and it never shows in the [reward fulfilment](Reward-Fulfilment.md) owed list — there's nothing to hand over.
- Only `homeassistant.turn_off` is ever called, and only on the devices you listed for that child. A `binary_sensor` is watched but never switched.

---

## On the Child Card

A strip shows the balance — *"1 h 15 min of screen time left"* — with a red dot while a device is on. It turns amber at the warning level and red at zero, when it points the child at the rewards. Hide it with the card option **Show screen-time balance**.

The same data is on `sensor.taskmate_overview`, in each child's entry under `screen_time`: `minutes`, `active` and `low`, plus `allowance` (today's allowance left, when there is some) and `jar` (`minutes`, `cap`, `day` with Monday as 0, and `at`) while the jar is on. It's only there while the bank is on.

---

## Automations

### `taskmate.adjust_screen_time`

Add minutes, or take some away with a negative number. Parent action.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | The child |
| `minutes` | ✅ | −10080 to 10080 |
| `reason` | ❌ | A short note for the balance history |

```yaml
# Half an hour free every Saturday morning
triggers:
  - trigger: time
    at: "08:00:00"
conditions:
  - condition: time
    weekday: sat
actions:
  - action: taskmate.adjust_screen_time
    data:
      child_id: "<child_id>"
      minutes: 30
      reason: Weekend bonus
```

### `taskmate.save_screen_time`

Move unused minutes into the jar. Linked-child check, like `complete_chore`, so a child's own login can use it.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | The child |
| `minutes` | ❌ | How many; leave out to save everything that fits |

### Events

| Event | Fields |
|-------|--------|
| `taskmate_screen_time_changed` | `child_id`, `child_name`, `delta`, `minutes`, `reward_id` (from a reward only), `timestamp` |
| `taskmate_screen_time_low` | `child_id`, `child_name`, `minutes`, `timestamp` |
| `taskmate_screen_time_out` | `child_id`, `child_name`, `minutes` (0), `timestamp` |
| `taskmate_screen_time_saved` | `child_id`, `child_name`, `minutes`, `jar`, `balance`, `timestamp` |
| `taskmate_screen_time_jar_opened` | `child_id`, `child_name`, `minutes`, `balance`, `timestamp` |

All of them show on the child's [event entity](Event-Entities.md).

### Notifications

| Notification | Type id | Goes to | Default |
|---|---|---|---|
| **Screen time running low** | `screen_time_low` | The child and parents | Off |
| **Screen time ran out** | `screen_time_out` | The child and parents | Off |
| **Screen-time jar opened** | `screen_time_jar_opened` | The child and parents | Off |

---

## Related

- [Timed Unlock Rewards](Timed-Unlock-Rewards.md) — a reward that switches something on for a fixed time
- [Managing Rewards](Managing-Rewards.md)
- [Event Entities](Event-Entities.md)
