# Child Stages

Children grow into chores at their own pace. A child's **stage** follows what they can already do, not their birthday, and the child card follows it: picture tiles for the youngest, a calmer card for teenagers. Each chore can also be marked **Can do**, **Practising** or **Later** for each child, so the card puts what they're learning first and keeps what's not for them yet out of the way.

---

## The Four Stages

**TaskMate panel → Children → Edit → Stage**

| Stage | Roughly | What the child is working on |
|-------|---------|------------------------------|
| **Joining in** | 2–5 | Taking part with an adult nearby |
| **Doing my part** | 6–9 | Small tasks alone, taking turns |
| **Contributing** | 10–12 | Seeing their own progress, proposing ideas |
| **Taking ownership** | 13–16 | Their own habits, a say in agreements |

The ages are loose guides. Pick the stage that matches the child, not the number.

The stage is the same setting the [Setup Wizard](Setup-Wizard.md) calls the age group, so a child set up in the wizard already has one. Nothing is migrated or renamed in storage (`age_group` stays `3_5` / `6_8` / `9_12` / `13_plus`). **Not set** is still allowed and changes nothing.

When a birthday moves a child into the next stage, the Today page says so: "Vaiha is 9 now and can try more on their own." The nudge only records the new stage; it never applies any suggestions.

---

## What a Stage Suggests

The suggestions are shown under the stage tiles in the child editor.

### Card behaviour

The [child card](Dashboard-Cards.md) reads the child's stage and uses it for any option **its own YAML leaves unset**. Anything you set on the card always wins.

| Stage | Child card default |
|-------|-------------------|
| Joining in | [Pre-Reader Mode](Pre-Reader-Mode.md) on (`pre_reader: true`) |
| Doing my part | Pre-Reader Mode off, chore descriptions shown (`show_description: true`) |
| Contributing | Pre-Reader Mode off |
| Taking ownership | Pre-Reader Mode off, no [roulette](Chore-Roulette.md) (`show_roulette: false`) and no confetti (`show_confetti: false`) |

`show_confetti` is a child card option too: set `show_confetti: false` on any child card to turn the tick-off burst off, whatever the stage. The card's visual editor leaves these four options out of the YAML until you change them, so a dashboard built in the editor keeps following the stage.

### Chore changes

Whether a stage may also change chores is your choice:

**Settings → Children → Stage suggestions change**

| Value | What happens |
|-------|--------------|
| **Card behaviour only** (`cards`, default) | A stage never touches chores |
| **Cards and chores** (`all`) | A stage change can also change that child's chores, once, after you confirm |

Today one stage has a chore change:

- **Joining in**: no deadlines or deductions. On chores assigned **only** to that child, the [mandatory](Mandatory-Chores.md) flag is switched off and the mandatory penalty and the late penalty are set to 0. A due time and its early bonus stay.

Chores shared with other children (or assigned to everyone) are **never** changed. The confirm lists them as left alone.

### Ideas

Some suggestions don't map onto a chore setting, so they're shown as ideas and never applied: about four chores a day for Joining in, rotation for shared jobs for Doing my part, [open-ended chores](Open-Ended-Chores.md) and [weekly targets](Weekly-Targets.md) for Contributing, and rewards worth saving up for at Taking ownership. Read Aloud has no per-child switch, so stages don't change it.

---

## Changing a Stage

On a saved child, picking another stage opens a confirm:

- moving up: "**Isla can try more now**"
- moving down or clearing it: "**Change Isla's stage**"

It lists what the child card will follow and, with **Cards and chores**, exactly which of the child's chores would change. Then:

- **Change stage only**: saves the stage. The card follows it; no chore changes.
- **Change and apply**: saves the stage and makes the listed chore changes once. Only offered when there's something to change.

The stage is saved as soon as you confirm; you don't need to press Save on the child. Nothing is ever applied automatically, and after applying, every chore option stays yours to change.

---

## Can do, Practising, Later

**TaskMate panel → Children → Edit → Chores for <name>**

Every chore the child can see gets a three-way switch:

| State | On the child card |
|-------|-------------------|
| **Can do** (default) | Shown as usual |
| **Practising** | Shown first, in its own **Practising** section with a "With help counts too" tag. In Pre-Reader Mode the chores still come first, without the words |
| **Later** | Hidden from this child's card |

Two or three practising chores at a time works best. The marks are saved with the child (press **Save**), stored only for chores that aren't "Can do", and removed when a chore is deleted. They're per child: the same chore can be "Practising" for one child and "Can do" for another.

---

## For Developers

- The overview sensor's `children` rows carry `age_group` and `chore_stage` (`{chore_id: "practising" | "later"}`) only when set.
- `taskmate/update_child` accepts `chore_stage` (the whole map; chores left out are "Can do").
- `taskmate/apply_child_stage` (admin): `child_id`, `stage`, `apply` (bool), `preview` (bool). It returns the plan: `card`, `chore_items`, `tips`, `chores` (each with `changes: {field: [old, new]}`), `skipped_shared` and `applied`.
- The global setting is `stage_scope`: `cards` or `all`.

---

## Related

- [Children](Children.md)
- [Setup Wizard](Setup-Wizard.md)
- [Pre-Reader Mode](Pre-Reader-Mode.md)
- [Dashboard Cards](Dashboard-Cards.md)
