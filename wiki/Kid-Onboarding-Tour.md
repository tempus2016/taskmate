# Kid Onboarding Tour

The first time a child opens their Child card, or picks their face on the [Kiosk](Kiosk-Mode.md), TaskMate walks them round it. The card goes dark apart from one real part of it at a time, with a little bubble beside it saying what it's for: "Tap here when a job is done", "Points add up here".

It points at the real card, not a slideshow, and the card stays live underneath. A child can tap the very job the tour is pointing at.

---

## The Steps

| Step | Points at | Says |
|------|-----------|------|
| 1 | The card's header | Hi *name*! This is your jobs page |
| 2 | The first job that can be ticked off now (not one waiting for its time of day, already done or locked) | Tap here when a job is done. *Some jobs wait for a grown-up to check them first.* |
| 3 | The points readout (or a job's "+3" on the designed styles) | *Points* add up here |
| 4 | A streak on the card (a per-chore 🔥 tag or streak freezes; the Kiosk's day-streak tile) | Do jobs every day for a streak |
| 5 | The savings forecast or weekly goal (the Kiosk's next-reward tile) | Save *points* for rewards |

The words use your family's own points name, so a family that calls them "Coins" hears "Coins add up here".

**A step with nothing to point at is left out.** No streak on the card yet, rewards hidden, no jobs today — that step is skipped and the dots count only the steps that are left. A brand-new child usually sees the first three.

The bubble sits below the part it points at, or above it when there isn't room. On a very short card (one row of picture tiles), the card grows a little while the tour is open so the bubble doesn't cover what it's pointing at.

When a job is ticked off during the tour, the celebration comes first: the tour steps aside while the "AWESOME!" popup and confetti are showing, then comes back on the same step.

**Skip** ends the tour. **Next** moves on, and the last step says **Done**. On a keyboard, focus moves into the bubble: **Enter** is Next and **Esc** skips.

---

## Picture-Only (Pre-Reader) Cards

A card with [`pre_reader: true`](Pre-Reader-Mode.md) gets a shorter tour for children who can't read yet: three steps (tap your job, you get points, save up for a treat), each with one big picture, a few words and a big **OK!** button. The points step shows your points icon rather than a star.

If a [read-aloud speaker](#reading-it-aloud) is set and **Read each step aloud automatically** is on, each step is spoken as it appears, with no tap needed.

The Kiosk has no picture mode, so it always uses the standard tour.

---

## Reading It Aloud

When a read-aloud speaker is set in Settings, the bubble has a 🔊 button that reads the step out on that speaker. It goes through the same path as [Read Aloud](Read-Aloud.md), and the words come from TaskMate's own translations in the card's language. A child can only choose *which step* is read, never the words, so a child account can't make the speaker say anything it likes.

With no speaker set, there's no 🔊 button.

---

## Once Per Child

When a child finishes or skips the tour, TaskMate saves it **against the child**, so they don't see it again on their phone after doing it on the kitchen tablet. The browser also remembers it, so a shared kiosk won't replay it to the same child if the connection is down when they finish. That reminder is cleared as soon as Home Assistant has the answer, so **Show again** works on that tablet too.

A child can only mark their own tour (the same linked-account rule as ticking off their own chores). Resetting it is for grown-ups.

The tour doesn't start:

- on a TaskMate parent's own account (a non-admin parent in **Settings → Parents**), so a grown-up looking at a child's card doesn't use up the child's tour;
- in the admin panel's **View as child** preview;
- for adult profiles;
- on a card with `show_tour: false`.

If a grown-up does click through it on a shared screen, use **Show again** in Settings.

### Children Who Already Use TaskMate

On the first start after upgrading, every child who has already done a chore or earned points is marked as not needing the tour. They show in Settings as **Not needed (already using TaskMate)**, and **Show again** gives it to them if you want. Children who hadn't started yet, and every child added afterwards, get the tour.

---

## Settings

In **Settings → First-time tour**:

| Setting | Default | What it does |
|---------|---------|--------------|
| **Show a first-time tour on the Child card and Kiosk** (`tour_enabled`) | on | Turns the tour on or off for the whole family |
| **Read each step aloud automatically** (`tour_auto_read`) | on | Picture-only cards speak each step as it appears. Needs the speaker below |
| **Read-aloud speaker** (`read_aloud_media_player`) | empty | Where the 🔊 button talks. It's the same setting as the default speaker for `taskmate.read_aloud` |

Below these, **Per child** lists each child with **Finished** *date*, **Skipped at step** *N*, **Not needed** or **Not yet**, and a **Show again** button that clears it. The child sees the tour the next time they open their card.

There's no "show it again after a big update" switch: the tour explains the same five things in every version, so replaying it after an update wouldn't teach anything new.

---

## Card Option

Both the Child card and the Kiosk card take `show_tour` (default `true`). Set it to `false` to keep the tour off one card, for example a grown-up's own dashboard. It's also in each card's visual editor as **Show the first-time tour**.

```yaml
type: custom:taskmate-child-card
entity: sensor.taskmate_overview
child_id: <child_id>
show_tour: false
```

---

## For Automations and Developers

- The overview sensor carries `tour` at the top level while the tour is on (`speak: 1` when a speaker is set, `auto: 1` when auto-read is on too), and each child entry carries `tour_done` (`true` once finished or skipped). Both are absent while the tour is off. See [Sensor Reference](Sensor-Reference.md).
- WebSocket commands: `taskmate/tour/mark` (`child_id`, `status`: `done` / `skipped`, `step`) for the child, `taskmate/tour/speak` (`child_id`, `step`, `language`) for the child, and `taskmate/tour/reset` (`child_id`) for grown-ups.
- The step wording lives in the card translations under `notify.tour_*`, which is also where the spoken version comes from.

---

## Related

- [Dashboard Cards](Dashboard-Cards.md) — the Child card and its options
- [Kiosk Mode](Kiosk-Mode.md) — the shared wall tablet
- [Pre-Reader Mode](Pre-Reader-Mode.md) — picture-only cards
- [Read Aloud](Read-Aloud.md) — the speaker the tour talks through
- [Settings](Settings.md) — every setting in one place
