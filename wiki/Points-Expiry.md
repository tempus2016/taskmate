# Points Expiry

Optional. Points that aren't spent within a set number of days fade away, oldest first, with plenty of warning on the child's card. It nudges children to spend on something rather than hoard forever. It's **off** unless you switch it on.

---

## Setting It Up

**Settings → Points expiry** in the TaskMate panel.

| Setting | What it does |
|---------|--------------|
| **Expire unspent points** | Switches the feature on. Every child's current balance starts its clock that day, so nothing already saved expires by surprise |
| **Expire after (days)** | How long a point lasts unspent. 1 to 730, default 90 |
| **Warn the child (days before)** | How early the card warns, and when the optional notification goes out. 0 to 60, default 7. `0` turns the warning off |

Switching it off forgets everything it was tracking. Switching it back on starts every balance afresh that day.

---

## How It Counts

TaskMate keeps each child's balance as dated *lots*: "100 points from 20 March, 50 from 25 March". It checks them against the balance every time anything changes, and once a minute.

- **Points coming in** (chores, bonuses, adjustments) are a new lot dated today.
- **Points going out** (rewards, penalties, removals, gifts to a sibling, savings-jar deposits) are taken from the **oldest** lot first, so spending always uses the points closest to expiring.
- **Refunds and returned points** count as coming in: a refunded reward, a pool refund or an undone penalty starts its clock again that day. They never come back already part-expired.
- **Savings jars**: points put into a reward's [savings jar](Pool-Mode-(Savings-Jars).md) have left the balance, so they don't expire while they sit there.
- A balance at or below zero holds no lots.

When a lot is older than the expiry period it comes off the balance with a **Points expired** transaction, which can't be undone, and a `taskmate_points_expired` event.

---

## On the Child Card

Inside the warning window a strip shows *"40 Stars expire on Sunday — Spend them or they fade away"*. It shows on every card design. The same data is on `sensor.taskmate_overview`, in the child's entry under `points_expiry` (`points`, `date`). It's only there while points are about to expire.

---

## Notification and Events

- **Points about to expire** (`points_expiring`): goes to the child, once per expiry date, when it enters the warning window. Off by default; switch it on on the Notifications tab.
- `taskmate_points_expiring`: fires at the same moment, whether or not the notification is on.
- `taskmate_points_expired`: fires when points actually expire.

Both also appear on the child's activity [event entity](Event-Entities.md). See [Automations](Automations.md) for the payloads.
