# Multi Parent Approval Routing

By default every approval buzzes every parent. Two other modes are available via the `parent_routing` setting, for households where that gets noisy.

![Parent routing in the Notifications tab](images/panel-notifications.png)

| Mode | Behaviour |
|------|-----------|
| `all` *(default)* | Every enabled parent, as before |
| `home` | Only parents whose presence entity says they're here |
| `round_robin` | One parent per notification, rotating |

---

## Presence Entities

For `home` mode, give each parent a **presence entity** in the notification settings — a `device_tracker.*`, a `person.*`, or anything that reads `home` / `on` / `true` / `present`.

---

## Every Fallback Errs Towards Over-Notifying

An unseen approval is worse than a redundant buzz, so every failure path widens the audience rather than narrowing it:

- **Nobody home** → everyone is told, not nobody.
- **No presence entity set** → that parent counts as available and is never silently cut out.
- **Broken or unavailable presence sensor** → fails open.
- **Round-robin state pointing at a deleted parent** → starts from the beginning rather than wedging.

---

## Round-Robin Detail

Round-robin position is tracked **per notification type**, so a reward claim doesn't advance the chore-approval rotation. Each kind of approval keeps its own place in the queue.

---

## Children Are Never Affected

None of this touches child notifications. A reminder for a child must always reach that child — routing applies only to the parent-facing approvals.

---

## Related

- [Notifications](Notifications.md) — the full notification system, actionable callbacks and bus events
- [Quiet Hours](Quiet-Hours.md) — per-child do-not-disturb windows
- [Reminder Escalation](Reminder-Escalation.md) — nudge → reminder → parent alert
- [Parent Access](Parent-Access.md) — giving a second parent control without HA admin rights
- [Settings](Settings.md) — where `parent_routing` lives
