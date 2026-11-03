# Week Planner

Plan the whole week on one screen: seven day columns, every chore on the days it falls, and drag a card to another day or another child. Nothing changes until you press **Save week**, so you can try things out and throw them away.

**TaskMate panel → Earn → Planner**

---

## What You See

- **Seven days, Monday to Sunday.** **‹** and **›** step a week back or forward; **This week** comes home. Today's column is outlined.
- **A card per chore per day**, with its icon, name and points. The coloured edge on the left is the child it belongs to that day; a purple edge means it's shared (everyone, or more than one child).
- **Striped cards** repeat on their own rhythm: daily chores and [recurring](Chore-Scheduling.md#mode-b-recurring) ones (every few days, weekly on a day, monthly…). Plain cards are on set weekdays or are one-off.
- **Turn-taking chores** show whose turn it is that day, worked out the same way as the rest of TaskMate. A chore [won at auction](Chore-Auctions.md) shows the winner.
- **A footer under each day** with the points each child can earn that day (their initial and a number) and the estimated minutes of work, so a lopsided day stands out. Minutes come from each chore's [estimated minutes](Estimated-Minutes.md), counted once per child doing it.
- **Not on this week** lists active chores that don't fall anywhere in the week, and **One-off** lists one-off chores dated in another week.

Pick a child with the name chips at the top to see their week: their chores stay bright and everyone else's fade. It's the same [child filter](Admin-Panel.md#child-filter) the rest of the panel uses, and adult profiles aren't offered here.

Which chores fall on which day follows the same rules as the [calendar](Calendar.md), including occurrences moved on the [two-way calendar](Two-Way-Calendar.md). Like the calendar it is the schedule only: [weather](Weather-Aware-Chores.md), [visibility](Dynamic-Chore-Visibility.md) and other live conditions are decided on the day.

---

## Moving Chores

Drag a card with the mouse. On a tablet, press and hold a card for a moment until it lifts, then drag it; a quick swipe that starts on a card still scrolls the page. While you drag, a note next to the card says what the drop will do, and the day under the pointer is highlighted. Hold the card near the top or bottom of the page to scroll it.

| You drag | onto | What it plans |
|---|---|---|
| A chore on set weekdays | another day | That weekday moves: *Walk dog: Tuesday → Wednesday, every week* |
| A chore on set weekdays, holding **Alt** (**⌥ Option** on a Mac) | another day | The day is added and the original stays: *also on Wednesday* |
| A chore from **Not on this week** | a day | That weekday is added to it |
| A one-off chore | a day | Its date changes to that day |
| A repeating chore | another day | You're asked: **This week only** or **The whole series** (below) |
| Any chore | a child's initial in a day's footer | The chore is given to that child (and moves to that day if it isn't there) |

With a child picked at the top, dropping a chore also gives it to that child, where the chore allows it.

### Repeating chores: this week only, or the whole series?

- **This week only** moves just that one occurrence, exactly like dragging it on the [two-way calendar](Two-Way-Calendar.md). Next time it's back on its usual rhythm. Only an occurrence from today onwards can move on its own.
- **The whole series** moves the rhythm with it. A weekly chore pinned to a day changes day; an every-few-days or monthly chore shifts its start date by the same number of days, so it lands where you dropped it and repeats from there.
- Dragging a repeating chore from **Not on this week** offers **Start the series here**: it starts again on that day.

### What the planner won't do

It refuses, with a message, anything that would quietly change more than you meant:

- dropping a chore on a day it's already on (nothing would change, or two days would merge into one);
- copying a one-off or a repeating chore to an extra day (a one-off only moves; a series has no "extra day");
- moving a daily chore to another day (it's already on every day);
- any change after which the chore wouldn't actually fall on the day you dropped it on, for example a chore that only starts next month.

Chores that **take turns** (alternating, random, balanced) or wait to be **picked up** (unassigned) keep their rotation: the planner moves their day but doesn't hand them to one child. Change who's in the rotation in the chore editor.

---

## Saving

Every change you make is listed in words in the dark bar at the bottom: *Hoover lounge: Tuesday → Wednesday, every week · Bins out: Vaiha → Malia*. Cards with an unsaved change are outlined.

- **Discard** throws every planned change away.
- **Save week** saves them all at once. Each chore is checked on its own: if one can't be saved (say a one-off's day has passed since you planned it), the bar shows why and keeps that change, and all the others are still saved.

Changes are kept while you look at other weeks or other pages of the panel, until you save or discard them.

---

## On a Phone

On a narrow screen the planner shows one day at a time with a strip of the seven days to pick from (with the number of chores on each). Dragging is off; instead each card has a **⋮** button with **Move to**, **Also on** and **Give to**. Cards in **Not on this week** offer **Add to**. The ⋮ button is on tablets and other touch screens too, always shown, and on desktop: hover a card or tab to it.

---

## Printing

**Print** opens the [printable weekly chart](Printable-Weekly-Chart.md) for the week you're looking at. It prints the saved schedule, so save first if you want your changes on paper.

---

## Related

- [Chore Scheduling](Chore-Scheduling.md) — set days, recurring and one-off chores
- [Two-Way Calendar](Two-Way-Calendar.md) — moving a single occurrence from Home Assistant's calendar
- [Estimated Minutes](Estimated-Minutes.md) — what the minutes in each day's footer add up
- [Admin Panel](Admin-Panel.md) — the rest of the panel
