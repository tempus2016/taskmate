# Sibling Checks

An older child can check a younger one's chore instead of a grown-up, for a small bonus. Parents can still overrule.

---

## Setting It Up

**Settings → Sibling checks** in the TaskMate panel:

| Setting | What it does |
|---------|--------------|
| **Turn on sibling checks** | The switch for the whole feature |
| **Points per check** | Paid to the checker each time they say **Looks done**. 0–50, default 1 |
| **<Name> can check** | For each child, tick the brothers and sisters they may check. A child can never check themselves |

Only parents can change who checks whom.

---

## On the Card

A checker's [child card](Dashboard-Cards.md#child-card) lists their siblings' chores that are waiting for approval: *"Check for Malia — Tidy room · 16:05 · 📷"*, with two buttons:

- **Looks done (+1)** approves the chore through the normal approval path, so the sibling gets their points, streak and badges exactly as if a parent had approved it. The approval is marked as a sibling check and the checker gets the bonus.
- **Not yet** leaves the chore waiting for a parent. The panel's approval queue then says *"👀 Vaiha says not yet"* beside it.

Only ordinary chores waiting for approval are listed — not [open-ended](Open-Ended-Chores.md) chores (a parent prices those), bonus sub-tasks or bounties — and each can only be checked once. At most five show at a time.

---

## Parents Keep the Last Word

- A chore a sibling approved can still be **rejected** or have its **approval undone** like any other.
- The bonus is an ordinary points transaction (*"Sibling check: Tidy room"*). Undo it from the activity list if the check wasn't honest.
- Every check is logged in the activity feed: *"Vaiha checked Malia's chore — looks done"*.

---

## Safety

The `taskmate.sibling_check` service uses the same linked-child rule as completing a chore, applied to the **checker**. TaskMate then checks on the server that sibling checks are on, that the checker is allowed to check that child and that it isn't their own chore. See [Parent Access](Parent-Access.md).

---

## For Automations

`taskmate_sibling_check` fires on every check — see [Automations](Automations.md). The approval it makes also fires `taskmate_chore_approved`, with `checked_by` set to the checker's id.

---

## Related

- [Services](Services.md#taskmatesibling_check)
- [Approvals Card](Approvals-Card.md)
