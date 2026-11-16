# Multipart Chores

A multipart chore is one chore with several **required steps**. The child ticks the steps off one at a time, and the chore's points are awarded only when **every** step is done. The steps live inside the chore, so the chore list stays short, and they walk the child through the job.

"Tidy bedroom" might have the steps *Clothes in the wash basket*, *Toys in the box* and *Make the bed*. The child sees one chore with "0/3 steps", ticks each step as they go, and gets the chore's points when the last one is ticked.

Multipart chores are different from two similar features:

- [Bonus Subtasks](Bonus-Subtasks.md) are **optional** extras that unlock after the chore is done and earn their own points.
- [Routines](Routine-Mode.md) group **separate chores**, each with its own points.

Steps earn nothing on their own.

---

## Setting up steps

1. Open the TaskMate panel and edit (or add) a chore.
2. Under **More**, open **Steps (multipart chore)**.
3. Click **+ Add step** for each step, and type its name. Use the ↑ and ↓ buttons to put the steps in order, and ✕ to remove one.
4. Save the chore.

A chore can have up to 20 steps. Leave the list empty for an ordinary chore.

A timed task and a chore with set times can't have steps, because neither is finished with a single tap that the last step could stand in for. Every other chore setting works with steps: approval, photo proof, open-ended notes, quantity, teamwork, weekly targets, streaks and so on.

---

## On the child card

- The chore row shows how far the child has got, for example **2/4 steps**.
- Tapping the chore (or its Done button) opens the checklist instead of completing the chore. Each step has a big numbered box to tick.
- Ticking a step again unticks it, as long as the chore isn't finished yet.
- Ticking the **last** step completes the chore through the normal path. If the chore needs a photo, a note or a number, the card asks for it then. Approval, points, streaks and the celebration all work as for any other chore.
- In **pre-reader mode** the tile shows one dot per step, filled in as steps are ticked. The checklist uses larger numbered boxes and leaves out the instructions text.

The checklist works on every card design style.

The **kiosk card** doesn't show the checklist. It lists a multipart chore with the chores to do on the child's own card, like photo-proof chores.

---

## How progress is kept

- Ticks are kept per child and per day. They reset at midnight.
- For a chore that can be done more than once a day, each go starts with a fresh checklist.
- If a completion is undone, or a parent rejects it, the ticks come back, so the child can submit again without ticking everything again.
- If a parent removes a step, ticks on the other steps are kept. A new step starts unticked.

A **parent completing on behalf** of a child doesn't need the steps ticked.

A child can't skip the steps from elsewhere either. The chore's button entity, an NFC tag or a `complete_chore` call is refused with "Finish every step of … first" until every step is ticked. The [`complete_next_chore`](Services.md) watch shortcut skips multipart chores.

---

## Service

### `taskmate.set_chore_step`

Tick or untick one step for today. The chore itself is then completed with `taskmate.complete_chore`.

| Field | Required | Description |
|-------|----------|-------------|
| `chore_id` | Yes | ID of the multipart chore |
| `child_id` | Yes | ID of the child |
| `step_id` | Yes | ID of the step |
| `done` | No | `true` (default) ticks the step, `false` unticks it |

```yaml
service: taskmate.set_chore_step
data:
  chore_id: b3f9a12c
  child_id: a8c8376a
  step_id: 4d2e91f0c7a1b3e5
```

A child linked to a Home Assistant user can only tick their own steps, the same rule as completing a chore.

---

## Sensor attributes

Only chores with steps carry these fields in the chores sensor's `chores` list:

| Field | Description |
|-------|-------------|
| `steps` | The steps in order, each with `id` and `name` |
| `step_done` | `{child_id: [step_id, …]}`: the steps each child has ticked on the current go. Left out while nobody has ticked any. |

---

## Related

- [Chores](Chores.md): chore configuration
- [Bonus Subtasks](Bonus-Subtasks.md): optional extra-credit tasks
- [Services](Services.md): full service reference
