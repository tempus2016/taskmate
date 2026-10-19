# Chore Dependencies

Chore dependencies let you chain chores together so one only becomes available after others are finished. A chore with dependencies stays locked until **every** chore it depends on has been completed and approved **today** by the **same child** — then it unlocks for that child.

![The Chores tab, where dependencies are set](images/panel-chores.png)

This turns a loose list of chores into an ordered routine: tidy the room *before* vacuuming, clear the table *before* loading the dishwasher.

---

## How It Works

Each chore can list one or more **prerequisite chores** it depends on (the `depends_on` field — a list of chore IDs). The dependent chore is only available to a child when **all** of its prerequisites are satisfied for that child:

- Each prerequisite must have an **approved** completion (a pending, not-yet-approved completion does not count).
- The completion must have been made **today**, by the **same child** who is trying to do the dependent chore.
- Parent chore completions count; bonus sub-task completions do **not**.

Because the check is evaluated **per day**, dependencies reset every night. Yesterday's approved prerequisites don't carry over — the child has to work back up the chain each day. If a prerequisite is rejected (or an approval is undone), the dependent chore locks again until the prerequisite is re-completed and re-approved.

---

## Setting Dependencies

Open the chore editor in the **Admin Panel → Chores → Edit chore**. Below the assignment options there's a **"Depends on"** picker listing your other chores. Tap a chore to mark it as a prerequisite; tap again to remove it. (A chore can't depend on itself, so it never appears in its own list.)

The editor hint sums it up: *"This chore stays hidden until the selected chores are approved for the child today."*

You can select several prerequisites — they must **all** be satisfied before the dependent chore unlocks.

---

## Effect on Availability and Visibility

Dependencies are one more gate on top of everything else that decides whether a child sees a chore. A chore that is scheduled and due today can still be **locked** purely because its prerequisites aren't done yet. Dependencies are checked alongside:

- The chore's schedule (see [Chore Scheduling](Chore-Scheduling.md)) — a dependent chore must still be due today *and* have its prerequisites met.
- Rotation assignment, vacation/away status, and per-child disabling.
- Any [Dynamic Chore Visibility](Dynamic-Chore-Visibility.md) entity condition.

While locked, how the dependent chore appears is controlled by the child card's **`dependency_mode`** option:

| Value | Behaviour |
| --- | --- |
| `hide` *(default)* | The chore isn't shown at all until it unlocks. Matches the backend, which simply reports it unavailable. |
| `dim` | Shown greyed out and not tappable, with a **"Do *X* first"** note naming the prerequisite, so the child can see what unlocks it. |
| `show` | Shown at normal opacity, still not tappable. |

Set it in the card editor under **Chores Waiting On Another**, or in YAML:

```yaml
type: custom:taskmate-child-card
entity: sensor.taskmate_overview
child_id: <child_id>
dependency_mode: dim
```

Under every mode the tap is refused, on all six card designs and in picture mode — the backend would reject the completion anyway. Once the last prerequisite is approved, the chore unlocks for the child on the next refresh.

---

## Example

A bedtime routine, all assigned to the same child:

1. **Tidy room** — no dependencies, available from the start of the day.
2. **Vacuum** — depends on *Tidy room*. Hidden until Tidy room is approved.
3. **Put out pyjamas** — depends on *Vacuum*. Hidden until Vacuum is approved.

The child can only ever see the next step in the chain, in order, and only after a parent has approved the previous one — each day afresh.

---

## Related

- [Chores](Chores.md) — the chore editor and the full list of chore fields
- [Chore Scheduling](Chore-Scheduling.md) — how a chore becomes due in the first place
- [Dynamic Chore Visibility](Dynamic-Chore-Visibility.md) — gating a chore on a Home Assistant entity state
