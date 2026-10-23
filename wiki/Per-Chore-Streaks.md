# Per-Chore Streaks

A streak on the chore itself, separate from the child's overall [streak](Streak-Freezes.md). The child card shows **🔥 12 days** on a chore row once a child has done that chore on two or more of its due days in a row.

---

## How It Counts

- **Only due days count.** A Monday/Wednesday/Friday chore isn't broken on a Tuesday, and a fortnightly one isn't broken in its week off. The same scheduling rules as the chore list decide which days a chore was due, calendar moves included.
- **Today counts once it's done.** Until then today is left out, so the tag doesn't drop to nothing first thing in the morning.
- **Waiting for approval counts.** A chore ticked off and still waiting for a parent keeps the streak going, the same way it does for the overall streak.
- **Days off don't break it.** A [holiday](Vacation-Mode.md), a [sick day](Sick-Days.md) or a [birthday day off](Birthday-Mode.md) (for chores that aren't mandatory) is skipped: it neither adds to nor breaks the streak.
- **Turn-taking chores.** On an alternating, random, balanced or first-come chore, a day a brother or sister did it is skipped rather than breaking the child's streak.
- **Weekly targets have no daily streak.** A chore with a [weekly target](Weekly-Targets.md) is owed by Sunday, not on any one day, so it never gets the tag.
- Bonus sub-tasks don't count. The streak looks back up to a year.

There is nothing to set up. The tag appears on the [child card](Dashboard-Cards.md#child-card) in every [design style](Card-Design-Styles.md).

---

## For Automations

The overview sensor's per-child summary carries `chore_streaks`: `{chore_id: days}` for streaks of two or more. A child with none has no `chore_streaks` key at all.

---

## Related

- [Streak Freezes](Streak-Freezes.md) — the child's overall streak
- [Personal Bests](Personal-Bests.md) — the longest overall streak as a record
