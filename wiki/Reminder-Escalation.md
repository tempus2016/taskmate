# Reminder Escalation

When a mandatory chore is left incomplete, TaskMate can step up its reminders over time instead of staying silent until the parent reviews the miss. The escalation ladder gives the child a gentle nudge first, reminds them again a while later, and finally alerts a parent if the chore is still not done.

![The Notifications tab](images/panel-notifications.png)

Added in v4.4.0.

---

## The Escalation Ladder

Each open same-day [mandatory miss](Mandatory-Chores.md) climbs a three-rung ladder based on how long it has gone unresolved:

| Stage | What fires | Audience | When |
|-------|------------|----------|------|
| 1 — Nudge | `mandatory_reminder` | The child | As soon as the miss is raised |
| 2 — Reminder | `mandatory_reminder` | The child | After the **reminder** threshold |
| 3 — Parent alert | `mandatory_parent_alert` | Parents | After the **parent** threshold |

The child rungs (stages 1 and 2) are sent **only to the affected child**, not fanned out to every routed recipient. The parent alert goes to the parent recipients you have routed for it.

If the child completes the chore at any point, that miss stops climbing the ladder.

TaskMate re-evaluates open misses on a short periodic tick (roughly every five minutes), so a chore that crosses a threshold is escalated promptly without any automation of your own. Only **same-day** misses are escalated.

---

## Configuring the Thresholds

Two thresholds, both in minutes, control when stages 2 and 3 fire. They are measured from the moment the miss was raised:

| Setting | Default | Meaning |
|---------|---------|---------|
| `mandatory_escalation_reminder_minutes` | `30` | Minutes after the miss before the **second** child reminder fires |
| `mandatory_escalation_parent_minutes` | `120` | Minutes after the miss before the **parent alert** fires |

Set both in the **Admin Panel → Notifications** tab, under the mandatory-reminder controls (**"Remind again after"** and **"Alert parent after"**). Each accepts a value from **1 to 1440** minutes.

---

## Enabling the Notifications

The two notification types are **off by default**. To use escalation, enable them in the **Admin Panel → Notifications** tab and route them to the right recipients:

1. Enable the **Mandatory reminder** type and route it to the children who should receive nudges.
2. Enable the **Mandatory parent alert** type and route it to the parent recipients who should be alerted.

Each stage is gated by its own master toggle and routing — stages still advance internally even when a type is disabled, so re-enabling a type later won't retro-fire skipped reminders.

---

## Quiet Hours

The child nudge and reminder respect [Quiet Hours](Quiet-Hours.md): because they are sent only to that child, they are held back while the child is inside their do-not-disturb window. The parent alert is a parent notification and is never suppressed by a child's quiet hours.

---

## Related

- [Mandatory Chores](Mandatory-Chores.md) — how a miss is detected and reviewed
- [Notifications](Notifications.md) — the notification system and routing
- [Quiet Hours](Quiet-Hours.md) — the per-child do-not-disturb window the nudge respects
- [Presence-Aware Reminders](Presence-Aware-Reminders.md) — hold reminders while a child is out, and the parent alert until they're home
