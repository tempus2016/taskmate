# Quiet Hours

Quiet hours let you set a per-child do-not-disturb window. While a child's local time is inside their window, TaskMate suppresses **that child's** notifications — so you don't ping them during school or after bedtime. Parent notifications are never affected.

![Quiet hours are set per child in the Notifications tab](images/panel-notifications.png)

Added in v4.4.0.

---

## What Quiet Hours Do

Each child can have a daily quiet-hours window defined by a start and end time. While the current local time falls inside that window:

- **The child's notifications are held back** — any notification routed to that child (bedtime reminders, streak-at-risk alerts, mandatory nudges, and so on) is silently skipped for the duration of the window.
- **Parents are unaffected** — quiet hours only gate child recipients. Parent recipients (and the underlying bus event) still fire as normal.

Quiet hours are checked at send time against the Home Assistant local clock, so a notification that would otherwise fire is simply not delivered to a child who is inside their window.

---

## How the Window Works

A window is two times in 24-hour `HH:MM` form:

| Field | Description |
|-------|-------------|
| `quiet_hours_start` | Start of the window (inclusive), e.g. `20:00`. Empty = quiet hours disabled. |
| `quiet_hours_end` | End of the window (exclusive), e.g. `07:00`. Empty = quiet hours disabled. |

Rules:

- **Both** times must be set. If either is empty, quiet hours are off for that child.
- The **end is exclusive** — a notification at exactly the end time is allowed through. A window with equal start and end (e.g. `07:00`–`07:00`) is treated as disabled.
- If the **start is later than the end**, the window is **overnight** — it runs from the start time, through midnight, to the end time the next morning. For example `20:00`–`07:00` covers every evening through to the following morning.
- If the start is earlier than the end, it's a same-day window (e.g. `08:30`–`15:00` to stay quiet during the school day).

---

## Setting Quiet Hours

Quiet hours are set per child in the **Admin Panel → Notifications** tab, alongside each child's notify service. Each child row has a **Quiet hours** start and end time picker — fill in both to enable the window, or clear them to turn it off.

---

## Example Windows

| Use case | Start | End |
|----------|-------|-----|
| Quiet overnight (bedtime) | `20:00` | `07:00` |
| Quiet during the school day | `08:30` | `15:30` |
| Quiet over lunch only | `12:00` | `13:00` |

---

## Interaction with Escalation

The mandatory-chore nudge (the first rung of [Reminder Escalation](Reminder-Escalation.md)) respects quiet hours too — because it is sent only to the affected child, it is held back while that child is inside their window. The parent alert at the top of the escalation ladder is a parent notification and is never suppressed.

---

## Related

- [Children](Children.md) — the per-child fields, including quiet hours
- [Notifications](Notifications.md) — the notification system that honours quiet hours
- [Reminder Escalation](Reminder-Escalation.md) — the mandatory-chore nudge that respects quiet hours
