# Child-Chosen Reminders

A child picks when they want nudging about a chore — *"remind me about homework at 17:30"* — and parents set the earliest and latest times allowed.

---

## Setting It Up

1. **Settings → Children's own reminders** in the TaskMate panel: turn on **Let children set reminders** and set the **Earliest time** and **Latest time** (default 15:00–20:00).
2. **Notifications → Reminder a child chose:** switch it on and route it to each child's phone. Like every notification added after the first release it starts off.

---

## On the Card

Each chore still to do gets a **🔔 Remind me** tag on the [child card](Dashboard-Cards.md#child-card). Tapping it opens a sheet with on-the-hour times inside the parent's window and a **Pick a time** box for anything else. Once set, the tag reads **🔔 17:30**; tap it to change the time or choose **No reminder**. Hide it on one card with `show_reminders: false`; pre-reader mode never shows it.

---

## When It's Sent

At the chosen time, on days the chore is due for that child and not done yet (waiting for approval counts as done), TaskMate sends *"⏰ Time for Homework, Vaiha — you asked me to remind you!"* to that child **only**. Once a day at most. [Quiet hours](Quiet-Hours.md) still apply.

---

## Services

`taskmate.set_chore_reminder` with `child_id`, `chore_id` and `time` (`HH:MM`, or empty to clear). It uses the same linked-child rule as completing a chore; the time has to be inside the parent's window and the chore has to be one of the child's. See [Services](Services.md#taskmateset_chore_reminder).

The overview sensor's per-child summary carries `reminders`: `{chore_id: "HH:MM"}`, and the overview carries `chore_reminders` (the earliest and latest time) while the feature is on.

---

## Related

- [Notifications](Notifications.md)
- [Reminder Escalation](Reminder-Escalation.md) — parent-set reminders for mandatory chores
