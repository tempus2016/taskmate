# Choice Sets

A choice set is a list of chores with a promise attached: **do at least N of these today, and you pick which**. "Your part for the family: at least 2 of these 5" gives a child a real choice while still making sure something gets done.

The chores inside a set stay ordinary, voluntary chores. What the child owes is the set, never one particular chore.

---

## How It Works

- Each day the child needs to do **at least N different chores** from the set. Doing the same chore twice counts once.
- A completion that is **waiting for approval counts**, so a child is never caught out by a slow parent. If you **reject** it, the slot opens up again.
- Once the set is met, the child card says **"Done! You can do more if you like."** The other chores stay open and pay as usual.
- If fewer chores are on offer today than N (some are off today, hidden or not assigned to this child), the set only asks for what is there. With **none** on offer, nothing is owed.
- A set with **Pick at least 0** is just a labelled group of optional chores. It can never be missed.
- Progress is counted from the day's completions. Nothing extra is stored.

### When a set is missed

At the end of the day (midnight), every child who didn't meet a set gets **one review item** for it: one per set, child and day, however many chores were in it. It goes to the same place as [missed mandatory chores](Mandatory-Chores.md) with the same three answers:

| Action | What happens |
|--------|--------------|
| **Apply penalty** | Takes the set's penalty points and clears the item |
| **Postpone** | Clears the item without a penalty ("not this time") |
| **Dismiss** | Clears the item without a penalty |

**Nothing is ever deducted automatically.** A parent decides every time. If you reject a set chore after midnight, the set is checked again and a review item appears if it is now unmet.

A day the child is off sick, away (vacation) or on a [birthday day off](Birthday-Mode.md) is never missed.

---

## Creating a Set

Choice sets live in **Admin Panel → Earn → Choice sets**.

| Field | Default | Description |
|-------|---------|-------------|
| **Name** | — | What the child sees above the set (required) |
| **Description** | `""` | Optional note for parents |
| **Icon** | `mdi:hand-heart-outline` | MDI icon |
| **Pick at least** | `1` | How many different chores from the set are needed each day. `0` = optional list, never missed |
| **Penalty if missed** | `0` | Points a parent may take from the review item. Never automatic |
| **Chores in this set** | — | At least one chore |
| **Assign to** | every child | Leave empty for every child. Grown-ups ([adult profiles](Adult-Profiles.md)) are left out unless you pick them |
| **Active** | `true` | An inactive set shows its chores as ordinary chores and is never missed |

### Which chores can join

- A chore can be in **one set only**.
- **Mandatory** chores can't join: they are owed on their own.
- **Rotation** (alternating, random, balanced), **first-come** and **planner pool** chores can't join: they belong to one child at a time.

The editor greys these out, and saving a set that breaks a rule is refused with a message that names the chore.

---

## Where Missed Items Are Reviewed

**Settings → Parents → Review missed chores in** decides where missed choice sets **and** missed mandatory chores wait:

| Setting | Where they show |
|---------|-----------------|
| **Approvals card** (default) | The [approvals card](Approvals-Card.md), as before |
| **Admin panel › Today** | The **Needs you** list on the panel's Today page. The approvals card leaves them out |
| **Both** | Both places. Resolving one clears it in the other |

---

## On the Child Card

Each set gets its own section on the [child card](Dashboard-Cards.md): the set's name, "Pick at least N", a row of dots and "x of N". The set's chores are listed only inside it, never twice. Any other chores follow under **Other chores**.

In [Pre-Reader Mode](Pre-Reader-Mode.md) the section shows the dots only, with the chores as picture tiles.

The kiosk and the routine card don't show sets yet; there the chores appear as ordinary chores.

---

## Streaks and Perfect Weeks

When **streaks need every chore** or **perfect week needs every chore** is on, a set counts as **one** due item: it is done once it is met. Its chores are never due on their own.

---

## Sensor Attributes

Each child in `sensor.taskmate_overview`'s `children` attribute carries a `choice_sets` list, only while a set applies to them:

| Field | Description |
|-------|-------------|
| `set_id` | The set's ID |
| `name` | Set name |
| `icon` | Set icon |
| `min` | Today's effective minimum (`min(Pick at least, chores on offer)`) |
| `done` | Different set chores done today (pending ones included) |
| `fulfilled` | `true` once `done` reaches `min` |
| `chore_ids` | The set's chores |

A missed set appears in `sensor.taskmate_pending_approvals`' `mandatory_misses` with a `set_id`, an empty `chore_id`, `set_name`, `set_done` and `set_min`. While **Review missed chores in** is not the approvals card, that sensor also carries `miss_review_location`.

---

## Services and Events

| Service | Fields |
|---------|--------|
| `taskmate.add_choice_set` | `name`, `chore_ids`, optional `min_required`, `description`, `icon`, `assigned_to`, `penalty_points`, `active` |
| `taskmate.update_choice_set` | `set_id` plus any field above |
| `taskmate.remove_choice_set` | `set_id` |

Resolve a missed set with the mandatory-miss services: `taskmate.apply_mandatory_penalty`, `taskmate.postpone_mandatory_chore`, `taskmate.dismiss_mandatory_chore` (each takes `miss_id`).

| Event | Data |
|-------|------|
| `taskmate_choice_set_fulfilled` | `set_id`, `set_name`, `child_id`, `child_name`, `chore_id`, `done`, `min`, `timestamp` |
| `taskmate_choice_set_missed` | `miss_id`, `set_id`, `set_name`, `child_id`, `child_name`, `done`, `min`, `penalty_points`, `date`, `timestamp` |

Both also show on each child's activity [event entity](Event-Entities.md).
