# Cooperative Setup (Team Style)

Some families see chores as everyone's contribution to the home, not as a game to win. **Team style** sets TaskMate up that way in one step: shared goals up front, no ranking between children and no automatic deductions.

You'll find it at the top of the admin panel's **Settings** page, under **Family style**, and as an optional page in the [setup wizard](Setup-Wizard.md).

---

## The Three Styles

| Style | What it does | Good fit |
|-------|--------------|----------|
| **Game** *(default)* | All game mechanics available. This is how TaskMate has always worked. | Children enjoy competition and surprises, or you are building new routines. |
| **Team** | Shared goals up front. No ranking between children and no automatic deductions. | Your family sees chores as a joint contribution. |
| **Custom** | You choose each feature yourself. | You already know what you want. |

A style only switches options. It never deletes anything: points, history, badges, penalties and raffles you created all stay where they are, and every option stays editable afterwards.

---

## What Team Style Changes

Picking a style first shows a summary of exactly what will change. Nothing happens until you press **Apply**.

| Option | Team style |
|--------|------------|
| Leaderboard and rank medals | Off |
| [Penalties](Penalties.md) | Off |
| [Points decay](Points-Economy.md) | Off |
| [Raffles](Raffles.md) | Off |
| [Chore roulette](Chore-Roulette.md) | Off |
| [Surprise inspections](Surprise-Inspections.md) | Off |
| [Family goal](Family-Goals.md) | On |
| [Help button](Help-Requests.md) on child cards | On by default, even in [Pre-Reader Mode](Pre-Reader-Mode.md) |

Chores, points, rewards, approvals, streaks, [teamwork chores](Teamwork-Chores.md) and [gifting](Gifting-Points.md) are unchanged.

Set the family goal's name, target and reward in **Settings** so the children have something to work towards together, and add the [Family Goal card](Family-Goals.md) to their dashboard.

### What the cards show

- The **Leaderboard** card shows a short "turned off" note instead of a ranking, and the **Points Display** card drops its rank medals.
- The **Penalties** and **Raffle** cards show a short note instead of their lists.
- An admin viewing one of these cards also sees where to turn it back on.

The penalty services still work, so a parent can still apply a penalty by hand from the admin panel or an automation.

### The help button

Under Team style a child card shows the "I'm stuck" button unless its YAML says otherwise. An explicit `show_help_button: false` (or `true`) in the card's YAML always wins.

---

## Cards Only, or the Admin Panel Too

**When a style turns a feature off** decides how far the hiding goes:

- **Cards only** *(default)*: Penalties, Raffles and the rest stay in the admin menu, so a parent can still use them by hand.
- **Cards and admin panel**: their tabs (Penalties, Raffles) also leave the admin menu until the style changes. The data is kept either way.

Press **Save settings** after changing it.

---

## Going Back to Game Style

Choosing **Game** turns the game features back on exactly as they were before you applied Team style. TaskMate keeps a note of those values when Team is applied, so a roulette or points decay you had set up comes back as it was. If there is no such note (for example, the family went straight to Custom), Game uses TaskMate's defaults.

---

## Custom

Change any of the options a style covers by hand, and the style becomes **Custom**. Choosing Custom yourself changes nothing: each option keeps its current value.

The leaderboard, penalties and raffles switches live in the **Family style** section. The others are in their own sections of Settings.

---

## For Automations and Templates

| Setting | Values |
|---------|--------|
| `family_style` | `game`, `team` or `custom`. Missing means the family never picked one and behaves as Game. |
| `style_hide_scope` | `cards` (default) or `both` |
| `leaderboard_enabled`, `penalties_enabled`, `raffles_enabled` | on by default |

The overview sensor carries `features_off` (for example `["leaderboard", "penalties"]`) only while something is off, and `family_style: team` only while Team style is on.

Admins can apply a style over the WebSocket API with `taskmate/apply_family_style` (`style`: `game`, `team` or `custom`). It returns the list of options it changed.
