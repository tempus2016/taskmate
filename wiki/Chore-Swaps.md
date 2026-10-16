# Chore Swaps

Chore swaps let a child ask to take over today's turn of a rotation chore from a sibling. The request is pending until a parent approves it, at which point the chore is reassigned to the requester for the day.

![The Child card](images/card-child.png)

---

## When a Swap Is Possible

Swaps only apply to **rotation chores** — those using an `alternating`, `random`, `balanced`, or `first_come` [assignment mode](Chores.md#assignment-modes), where a single child holds today's turn.

A request is rejected outright if:

- The chore is in `everyone` or `unassigned` mode (there is no single turn to take over)
- The chore is already assigned to the requesting child today

---

## Requesting a Swap

There are two ways to request a swap:

- **From the child card** — see [From the Child Card](#from-the-child-card) below.
- **With the `taskmate.request_swap` service**, or from the chore row in the [Admin Panel](Admin-Panel.md) (**Request swap** button).

```yaml
service: taskmate.request_swap
data:
  chore_id: b3f9a12c
  requester_id: a8c8376a
```

| Field | Required | Description |
|-------|----------|-------------|
| `chore_id` | Yes | The rotation chore to take over |
| `requester_id` | Yes | The child who wants today's turn |

The service is linked-child gated — a child user can only request on their own behalf. The request is stored with a `pending` status, recording the requester, the child who currently holds the turn (`from_child_id`), and a timestamp.

---

## From the Child Card

Since v4.0.1, a child can request a swap directly from their [child card](Dashboard-Cards.md). Below the day's chores, a **Take over a chore** section lists the rotation chores whose turn belongs to a sibling today and that this child is in the pool for. Each row shows the chore name and its (post-multiplier) points, with a **Request** button.

Tapping **Request** calls `taskmate.request_swap` for that child and the button changes to **Requested** — the request then goes to the parent's approval queue. The section only lists chores in a rotation mode (`alternating`, `random`, `balanced`, `first_come`); `everyone` and unassigned chores never appear, and a child's own turn is never listed.

The section is gated by the child card's **`show_swaps`** option, which is **on by default**. Set `show_swaps: false` in the card config to hide it.

---

## Parent Approval

Pending swap requests appear to parents in the [Admin Panel](Admin-Panel.md) (with a count badge). For each, the parent can approve or reject:

| Action | What happens |
|--------|--------------|
| **Approve** | Today's turn is reassigned to the requester — the chore's current assignee becomes the requesting child for the day, recorded as a dated override on the chore. The request itself is then consumed. |
| **Reject** | The pending request is removed. The rotation is unchanged. |

On approval, TaskMate fires a `taskmate_swap_approved` event carrying `chore_id`, `requester_id`, and `from_child_id`.

Since v5.1.1 an approved request is **removed** rather than left in storage with an `approved` status. Nothing read a settled request, so those records accumulated for the life of the install; existing stores are swept clean on upgrade. The approval remains observable through the `taskmate_swap_approved` event and the chore's own dated override.

> **Completing a swapped chore.** Before v5.1.1, approval wrote only the chore's cached assignee field while every eligibility gate resolved the day's assignee from pure rotation maths — so the swapped-to child saw the chore on their card but tapping it did nothing at all: no completion, no points, no pending approval, and the chore returned within 30 seconds. Approval now stamps a dated override that the resolver honours, which fixes completion along with the per-chore button, the to-do list, streak and perfect-day accounting, and calendar publishing. This was broken from v4.0.0 (when swaps were introduced) until v5.1.1.

### When a Chore or Child Is Deleted

Deleting a chore drops any pending swap requests for it, and deleting a child drops any request they were the requester or the previous holder of. If an approved swap pointed at the deleted child, the chore's override is cleared and the chore is repointed at today's live pool immediately.

Before v5.1.1 neither delete path touched swap requests, which left the parent a permanent **"? wants to swap ?"** row in the approval queue that only rejecting could clear; and removing a child left their rotation chores pointing at a non-existent assignee, so those chores disappeared from every remaining child's card until midnight. Existing installs are swept clean on upgrade.

---

## Scope of a Swap

A swap changes **only today's assignment** of the chore. It does not alter the underlying rotation order or anchor — the next scheduled day follows the normal rotation algorithm as if the swap had not happened.

---

## Related

- [Chores](Chores.md) — chore configuration
- [Chore Scheduling](Chores.md#assignment-modes) — rotation assignment modes that swaps act on
- [Approvals-Card](Approvals-Card.md) — parent approval workflow
- [Services](Services.md) — full `request_swap` reference
