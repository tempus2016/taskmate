# Weekly Digest

The weekly digest is a Sunday-evening summary sent to parents recapping each child's week. It turns a week of activity into a single at-a-glance message.

![The Weekly card](images/card-weekly.png)

Added in v4.0.0.

---

## What It Contains

The digest lists one line per child showing how many chores they completed and how many points they earned over the week:

```
TaskMate weekly digest:
• Alex: 5 chores, 50 Stars earned
• Mia: 3 chores, 30 Stars earned
```

Counts are built from **approved** chore completions since the start of the current week (Monday). The points figure is the points awarded by those completions. **Bonus subtask** completions and **pending** (unapproved) completions are excluded, and only the current week is counted. The points label follows your configured points name (e.g. "Stars").

If there are no children, no digest is sent.

---

## Schedule

- The digest fires on **Sundays at 18:00** (local time).
- Internally a check runs daily at 18:00 and only sends on Sundays — no separate automation is required.

---

## Monthly Report

For a longer-period view, there is now also a **monthly report** (the `monthly_report` notification). It fires on the **1st of each month** at 18:00 and recaps the **previous calendar month** for each child — chores completed, points earned, level and best streak. Like the weekly digest it has the parent audience, is delivered through the standard [notification system](Notifications.md), and is **off by default**. Enable and route the **Monthly report** type on the Notifications tab the same way as the weekly digest.

---

## Audience & Target

The digest has the **parent** audience. It is delivered through the standard [notification system](Notifications.md), so it goes to the parent recipients you have enabled for the **Weekly digest** type in the recipient routing matrix, plus the usual persistent notification in Home Assistant.

---

## Enabling & Configuring

The weekly digest is a built-in notification type (`weekly_digest`) and is **off by default**.

1. Open the **Admin Panel → Notifications** tab.
2. Enable the **Weekly digest** type's master toggle.
3. In the recipient routing matrix, enable it for each parent recipient who should receive it.

You can verify routing without waiting for Sunday by using **Send test** on the Weekly digest row (see [Notifications — Testing a Notification](Notifications.md#testing-a-notification)).

The matching `taskmate_weekly_digest` bus event carries the rendered `summary` and the `recipients` list — see [Automations](Automations.md).

---

## Related

- [Notifications](Notifications.md) — the notification system that delivers the digest and monthly report
- [Admin Panel](Admin-Panel.md) — where to enable and route it
