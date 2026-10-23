# Tomorrow Preview

A **Today / Tomorrow** switch at the top of the child card's chore list, so a child can see what's coming before bed.

---

## How It Works

- **Tomorrow** lists the chores due for that child tomorrow, each with its points and a 🔒. They can't be ticked until the day; the list says so underneath.
- TaskMate works the list out with the same scheduling rules it uses for today: due days, recurring schedules, one-off chores dated tomorrow, turn-taking chores whose turn it is, chores won at auction and [calendar moves](Two-Way-Calendar.md). The card never guesses.
- The switch only appears when something is due tomorrow. On a [holiday](Vacation-Mode.md) or a [sick day](Sick-Days.md) nothing is due, so there is no switch.
- A [reminder time](Child-Chosen-Reminders.md) the child has set shows on the tomorrow row too.
- Chores with a [weekly target](Weekly-Targets.md) aren't listed: they're owed by Sunday, not on a day.

It works in every [design style](Card-Design-Styles.md). Hide it on one card with `show_tomorrow: false`. Pre-reader mode never shows it.

---

## For Automations

The overview sensor's per-child summary carries `tomorrow`: the chore ids due tomorrow, in the chores' own order. A child with nothing due tomorrow has no `tomorrow` key.

---

## Related

- [Chore Scheduling](Chore-Scheduling.md) — the rules behind the list
- [Calendar](Calendar.md) — the whole week at once
