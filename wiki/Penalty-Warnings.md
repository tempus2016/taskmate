# Penalty Warnings

A yellow card first: the points only go the second time.

---

## Setting It Up

Edit a penalty in the panel's **Penalties** tab. Under **Warning first**:

| Setting | What it does |
|---------|--------------|
| **Give a warning first** | The first time the penalty is applied in a period is only a warning |
| **Warning resets** | **Daily** (the default) or **Weekly** — when the slate is wiped clean |

---

## How It Works

1. The first time the penalty is applied to a child in the period, **no points are taken**. The child's card shows *"🟨 Warning: Shouting at the table — Next time it's −10 Stars"*, the panel says *"Warning given"*, and `taskmate_penalty_warning` fires.
2. The next time in the same period it deducts as normal (and the card strip goes). Every application after that deducts too.
3. When the period resets — the next day, or the next Monday for a weekly warning — the first application is a warning again.

The warning is per child and per penalty. It works however the penalty is applied: the panel, the [Penalties card](Dashboard-Cards.md) or `taskmate.apply_penalty`.

A penalty with a [make-it-right](Make-It-Right-Penalties.md) chore only offers it once points are actually taken.

---

## For Automations

`taskmate_penalty_warning` carries `child_id`, `child_name`, `penalty_id`, `penalty_name`, `points` (what next time costs) and `resets` (`daily` / `weekly`). It's also on the child's [event entity](Event-Entities.md) as `penalty_warning`. The overview sensor's per-child summary carries `penalty_warnings` while there's one to show.

---

## Related

- [Penalties](Penalties.md)
- [Appeals](Appeals.md)
