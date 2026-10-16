# Parent Access

Give a second parent day-to-day control of TaskMate **without** making them a Home Assistant administrator.

![Parents without admin rights are set in Settings](images/panel-settings.png)

Added in v4.5.0.

---

## The problem this solves

By default, every "parent" action in TaskMate — approving chores, adjusting points, confirming rewards — requires Home Assistant **admin** rights. Making a partner a full HA admin just to run the daily routine also gives them the ability to change unrelated Home Assistant configuration. The parent role closes that gap: it grants the day-to-day TaskMate controls and nothing more.

## Privilege tiers

| Tier | Who | Can do |
|------|-----|--------|
| **Admin** | Home Assistant admins | Everything, including the admin panel and all configuration. |
| **Parent** *(new)* | Non-admin HA users you designate | Day-to-day actions only (see below). |
| **Linked child** | An HA user linked to a child | That child's own self-service. |
| **Kiosk** | Unlinked / shared tablet | Open child self-service. |

## What a parent can do

Straight from the TaskMate cards, a designated parent can:

- Approve or reject chore completions — including **Approve All**
- Approve or reject reward claims
- Give, adjust or deduct points, gift points between children, and confirm allowance payouts
- Apply a [bonus](Bonuses.md) or a [penalty](Penalties.md) to a child *(since v5.0.4)*
- Award badges, and apply / postpone / dismiss mandatory-chore outcomes
- Complete a chore on a child's behalf
- Undo completions and approvals

## What a parent cannot do

- Open the TaskMate **admin panel** (`/taskmate-admin`) — it stays admin-only
- Create or delete children
- Edit chore, reward, badge, bonus or penalty **definitions** — applying an existing bonus or penalty is a daily action, but *defining* one is configuration
- Change any settings, designs, or Home Assistant user links
- Grant the parent role to anyone (only an admin can)

Every parent action is recorded in the [Admin Audit Log](Admin-Audit-Log.md) against the parent's Home Assistant user, so there is always a trail of who did what.

## Setting it up

1. In Home Assistant, create a normal **non-admin** user for the parent (Settings → People → Users), if they don't already have one.
2. Open the TaskMate admin panel → **[Settings](Settings.md)** → **Parents (no admin rights)**.
3. Tick that user in the list (admins are omitted — they already have full access) and **Save**.
4. Add the TaskMate cards to a dashboard the parent can reach. They will now see the parent controls (approve, reject, complete-on-behalf, adjust points) unlocked.

To revoke, untick the user in the same place and Save.

## How it works

The role is a list of Home Assistant user IDs stored in TaskMate's settings. The backend enforces it on every day-to-day service call — a caller who is neither an admin nor a listed parent is rejected with `Unauthorized`, so hiding a control in the UI is never the only line of defence. The cards read the list from the `sensor.taskmate_overview` entity to decide which controls to show.

See also [Child Undo Window](Child-Undo-Window.md) — an opt-in window in which children can undo their own chores.
