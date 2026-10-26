# Services

TaskMate exposes a set of Home Assistant services for automations, scripts, and custom frontend integrations.

Every service is in the `taskmate.*` namespace and accepts parameters via the standard `service_data` / `data` key.

## Dynamic Selectors (v3.7.0+)

All entity ID fields (`child_id`, `chore_id`, `reward_id`, `penalty_id`, `bonus_id`, `group_id`) show as **dropdown selectors** in the HA automation editor and Developer Tools → Services. The dropdown lists entity names as labels with the hex IDs as values, so you can pick "Noah" instead of typing `ef19c56175c14bd9`.

- Dropdowns refresh automatically every 30 seconds as entities are added or removed
- `custom_value` mode is enabled — you can still type a raw hex ID if you prefer
- Services without entity ID fields (e.g. `preview_sound`, `add_chore`) are unaffected
- Uses Home Assistant's native select widget — no custom styling

> **Tip:** If you need to find an ID outside the automation editor, enable the [Show IDs toggle](Admin-Panel.md#show-ids-v370) in the admin panel.

---

## Chore services

### `taskmate.complete_chore`
Mark a chore as completed by a child.

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `chore_id` | ✅ | — | ID of the chore |
| `child_id` | ✅ | — | ID of the child |
| `as_parent` |  | `false` | Complete on behalf of the child and award points immediately, bypassing approval (v4.0.0, #402). See [Photo Proof](Photo-Proof.md) for how this interacts with photo-required chores. |
| `photo_url` |  | — | Optional evidence photo URL/path attached to the completion. Required in spirit when the chore has [photo proof](Photo-Proof.md) enabled. |
| `note` |  | — | The child's own description of what they did (v5.7.0, #832). **Required** when the chore is [open-ended](Open-Ended-Chores.md). Trimmed to 200 characters. |
| `suggested_points` |  | `0` | What the child reckons the work was worth (v5.7.0, #832). A hint for the approving parent — it awards nothing on its own. Clamped to 0–999. |
| `quantity` |  | — | (v7.0.0) How many units the child did on a [quantity chore](Quantity-Chores.md) ("read 20 pages"), 0–10000. Required from a child on those chores; the chore's points are paid per unit, capped at the chore's maximum. Ignored on other chores. |
| `completed_date` |  | — | (v6.4.0) Log the job for an earlier day that was done but not ticked: up to 7 days back, not today. Parents only (an HA admin or a [TaskMate parent](Parent-Access.md); automations are allowed). Approved straight away and left out of the streak. See [Logging Past Jobs](Logging-Past-Jobs.md). |

```yaml
service: taskmate.complete_chore
data:
  chore_id: 8a3b2c1d4e5f6789
  child_id: ef19c56175c14bd9
  as_parent: false
  photo_url: "/local/proof/dishes.jpg"
```

> **Note:** `as_parent: true` records the completion under the parent (`__parent__`) and skips the approval queue. A chore with `require_photo` enabled always routes to approval so the photo can be reviewed.

Logging a job done on an earlier day (v6.4.0):

```yaml
service: taskmate.complete_chore
data:
  chore_id: 8a3b2c1d4e5f6789
  child_id: ef19c56175c14bd9
  completed_date: "2026-10-13"
```

The day's daily limit and the week's [weekly target](Weekly-Targets.md) still apply. The call is refused, with a message saying why, for a day the chore wasn't due, a vacation day, a rotation, teamwork or open-ended chore, or a day it was won at auction. An [adult profile](Adult-Profiles.md)'s own completions are always approved straight away, with or without `completed_date`.

### `taskmate.approve_chore`
Approve a completed chore and award points.

| Field | Required | Description |
| --- | --- | --- |
| `completion_id` | ✅ | ID of the pending chore completion |
| `points` | ❌ | Award this many points instead of the chore's own value (v5.7.0, #832). Replaces the **base** points, so the multipliers below still apply on top. Omit to use the chore's value. |
| `rating` | ❌ | (v6.0.0) A 1–3 star [quality rating](Quality-Ratings.md). When quality ratings are switched on in Settings, the points are scaled by that star's multiplier (by default ★ 75%, ★★ 100%, ★★★ 125%). Leave it out to pay 100%. Ignored while quality ratings are off. |
| `note` | ❌ | A [praise note](Praise-Notes.md) for the child, up to 120 characters, shown on their card today and signed with the approving user's name |

```yaml
service: taskmate.approve_chore
data:
  completion_id: 4f21b8e0c7a94d13
  points: 15
  rating: 3
```

Also accepted by the `taskmate/approve_chore` WebSocket command, which is what the review-and-award sheet on the [Approvals Card](Approvals-Card.md) calls. `approve_all_chores` never overrides — a bulk approval always uses each chore's own points.

### `taskmate.approve_all_chores` (v4.4.3+)
Approve every pending chore completion at once — or a specific set — and award points. Each approval runs the same award/badge/quest/streak/celebration side-effects as [`approve_chore`](#approve_chore). Admin-only.

| Field | Required | Description |
| --- | --- | --- |
| `completion_ids` | ❌ | List of specific completion IDs to approve. Omit to approve **all** currently-pending completions. IDs not currently pending are skipped. |
| `rating` | ❌ | (v6.0.0) A 1–3 star [quality rating](Quality-Ratings.md) applied to every chore approved by this call. Needs quality ratings switched on in Settings. |

Also exposed as the `taskmate/approve_all_chores` WebSocket command (same optional `completion_ids`), returning `{ "count": <number approved> }`. This is what the **Approve All** buttons on the panel and [Approvals Card](Approvals-Card.md) call.

### `taskmate.reject_chore`
Reject a completed chore. No points awarded.

| Field | Required | Description |
| --- | --- | --- |
| `completion_id` | ✅ | ID of the pending chore completion |
| `reason` | ❌ | (v6.0.0) Why it was sent back, up to 200 characters. The child sees "Sent back: …" on their card for 24 hours, and it is included in the `taskmate_chore_rejected` event and the optional **Item rejected** notification. See [Reject Reasons](Reject-Reasons.md). |

```yaml
service: taskmate.reject_chore
data:
  completion_id: 4f21b8e0c7a94d13
  reason: "Not finished — the bottom shelf is still messy"
```

### `taskmate.undo_chore` (v6.0.0)
Lets a **child** take back their own chore. Off until **Settings → Child undo window (seconds)** is set above `0`. See [Child Undo Window](Child-Undo-Window.md).

| Field | Required | Description |
| --- | --- | --- |
| `completion_id` | ✅ | ID of the child's chore completion |

- A submission still **waiting for approval** can be withdrawn until a parent reviews it.
- An **automatically approved** chore (no approval needed) can be undone within the window.
- Once a parent has reviewed it, only a parent can undo it (with `reject_chore` or `undo_chore_approval`).
- The child is taken from the stored completion, never from the call, so one child can't undo a sibling's chore when "Require a linked account per child" is on.

Fires `taskmate_chore_undone` (not `taskmate_chore_rejected`), so automations can tell a child's own undo from a parent's rejection.

### `taskmate.add_chore`
Create a chore dynamically (for automations).

| Field | Required | Description |
| --- | --- | --- |
| `name` | ✅ | Chore title |
| `description` |  | Optional details |
| `points` |  | Point value (default 10) |
| `assigned_to` |  | List of child IDs (empty = all) |
| `time_category` |  | `morning` / `afternoon` / `evening` / `night` / `anytime` (default `anytime`) |
| `difficulty` |  | Difficulty tier — `easy` / `medium` / `hard` (default `medium`). Scales awarded points by the tier multiplier; `medium` = ×1.0 baseline. See [Difficulty Tiers](Difficulty-Tiers.md). |
| `one_shot` |  | Single-day auto-expiring chore (boolean, default false) |
| `requires_approval` |  | Parent approval required (boolean, default true) |
| `expires_in_minutes` |  | (v5.0.0) Deadline this many minutes from now — makes it a [reactive chore](Reactive-Chores.md). `0` = no deadline. Max 10080 (a week). A chore with a deadline is automatically one-shot. |
| `speed_bonus_points` |  | (v5.0.0) Extra points if the chore is completed before the deadline |
| `team_size` |  | (v6.0.0) Make it a [teamwork chore](Teamwork-Chores.md) that only counts once this many children (2–10) have joined. `0` = a normal chore (default) |
| `team_points_mode` |  | (v6.0.0) `each` (everyone gets the full points, default) or `split` (the points are divided evenly, rounded down) |
| `team_bonus` |  | (v6.0.0) Extra points each team member earns when the team completes the chore (default 0) |

```yaml
service: taskmate.add_chore
data:
  name: "Take out recycling"
  points: 15
  difficulty: hard
  time_category: evening
  assigned_to:
    - ef19c56175c14bd9
```

> **Note:** Some advanced chore fields — `expires_on`, photo proof (`require_photo`), time incentives (`due_time` / `early_bonus` / `late_penalty`), weather conditions, and `first_come` assignment mode — are not exposed on the `add_chore` service. Configure them in the [Admin Panel](Admin-Panel.md) chore editor. See [Difficulty Tiers](Difficulty-Tiers.md), [Photo Proof](Photo-Proof.md), and [Chores](Chores.md).

### `taskmate.skip_chore`
Skip today's assigned child in a rotation-mode chore and reassign to the next child in the pool.

| Field | Required | Description |
| --- | --- | --- |
| `chore_id` | ✅ | ID of the chore |

Only works for non-`everyone` assignment modes with a pool of 2+ children. The skip is ephemeral — applies only today and resets at midnight. Maximum skips per day = pool size − 1. Sticky group followers cannot be skipped individually.

### `taskmate.set_chore_manual_start`
Override the rotation to start with a specific child.

| Field | Required | Description |
| --- | --- | --- |
| `chore_id` | ✅ | ID of the chore |
| `child_id` | ✅ | ID of the child to assign |

For `alternating` mode: reorders the rotation so the chosen child is first and resets the anchor to today. For `random`/`balanced` modes: overrides today's cached assignment only — the deterministic algorithm resumes tomorrow. Clears any active skip state.

### `taskmate.complete_bonus_subtask`
Complete a bonus subtask within a parent chore.

| Field | Required | Description |
| --- | --- | --- |
| `chore_id` | ✅ | ID of the parent chore |
| `bonus_subtask_id` | ✅ | ID of the bonus subtask |
| `child_id` | ✅ | ID of the child |

The parent chore must already be completed by the same child today. The subtask cannot already be completed by that child today. See [Bonus Subtasks](Bonus-Subtasks.md).

### `taskmate.request_swap` (v4.0.0)
A child requests to take over today's rotation assignment of a chore. Creates a pending swap request for a parent to approve. See [Chore Swaps](Chore-Swaps.md).

| Field | Required | Description |
| --- | --- | --- |
| `chore_id` | ✅ | ID of the chore (must be a rotation mode: `alternating` / `random` / `balanced` / `first_come`) |
| `requester_id` | ✅ | ID of the child requesting to take the chore over |

```yaml
service: taskmate.request_swap
data:
  chore_id: 8a3b2c1d4e5f6789
  requester_id: ef19c56175c14bd9
```

The requester must be a different child from today's current assignee and must be in the chore's pool. Approve/reject the request from the Admin Panel; on approval the chore's `assignment_current_child_id` is set to the requester. See [Chore Swaps](Chore-Swaps.md).

### `taskmate.leave_team_chore` (v6.0.0)
Take a child back out of a [teamwork chore](Teamwork-Chores.md) they joined today, before the team is complete. (Joining is just a normal `complete_chore` on a teamwork chore.)

| Field | Required | Description |
| --- | --- | --- |
| `chore_id` | ✅ | ID of the teamwork chore |
| `child_id` | ✅ | ID of the child leaving the team |

A child can only leave for themselves; parents can remove anyone. Leaving a team you hadn't joined, or one that has already completed, does nothing.

### `taskmate.complete_next_chore` (v6.0.0)
Complete the child's **next** outstanding chore, in the order their child card shows. Made for a watch button or a phone shortcut. See [Watch Complications](Watch-Complications.md).

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | ID of the child |

```yaml
service: taskmate.complete_next_chore
data:
  child_id: ef19c56175c14bd9
```

- Chores that need a photo, a note, a timer or a team are skipped.
- Approval rules apply exactly as if the child had tapped the chore.
- When nothing is left it quietly does nothing, rather than raising an error.

## Timed task services

### `taskmate.start_timed_task`
Start or resume a timed task timer.

| Field | Required | Description |
| --- | --- | --- |
| `chore_id` | ✅ | ID of the timed chore |
| `child_id` | ✅ | ID of the child |

Starts a new session or resumes a paused one. Checks the daily cap before starting.

### `taskmate.pause_timed_task`
Pause a running timed task timer.

| Field | Required | Description |
| --- | --- | --- |
| `chore_id` | ✅ | ID of the timed chore |
| `child_id` | ✅ | ID of the child |

Closes the current time segment and marks the session as paused. Resume with `start_timed_task`.

### `taskmate.stop_timed_task`
Stop a timed task and submit for approval.

| Field | Required | Description |
| --- | --- | --- |
| `chore_id` | ✅ | ID of the timed chore |
| `child_id` | ✅ | ID of the child |

Creates a completion record. Points are calculated as `floor(total_seconds / (rate_minutes × 60)) × rate_points`, clamped to the daily cap if set. See [Timed Tasks](Timed-Tasks.md).

## Task group services

### `taskmate.add_task_group`
Create a task group to coordinate rotation-mode chore assignments.

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `name` | ✅ | — | Group display name |
| `policy` | ✅ | `sticky` | `sticky` (same child) or `spread` (different children) |
| `chore_ids` |  | `[]` | Ordered list of chore IDs |

```yaml
service: taskmate.add_task_group
data:
  name: "Dinner Duties"
  policy: sticky
  chore_ids:
    - abc12345
    - def67890
```

### `taskmate.update_task_group`
Update an existing task group. Only supplied fields are changed.

| Field | Required | Description |
| --- | --- | --- |
| `group_id` | ✅ | ID of the group to update |
| `name` |  | New name |
| `policy` |  | New policy |
| `chore_ids` |  | New ordered chore list |

### `taskmate.remove_task_group`
Delete a task group. Chores revert to independent rotation.

| Field | Required | Description |
| --- | --- | --- |
| `group_id` | ✅ | ID of the group to remove |

See [Task Groups](Task-Groups.md) for full details on sticky and spread policies.

## Reward services

### `taskmate.claim_reward`
A child claims a reward. Creates a pending claim awaiting parent approval.

For **wallet-mode** rewards: child's balance must cover the cost.
For **pool-mode** rewards: the child's pool allocation must equal or exceed the cost (i.e. the pool is full).

| Field | Required | Description |
| --- | --- | --- |
| `reward_id` | ✅ | ID of the reward |
| `child_id` | ✅ | ID of the claiming child |
| `recipient_id` | ❌ | Buy it for a brother or sister instead: `child_id` pays, the recipient gets it. Needs **Children can buy rewards for each other**. See [Reward extras](Reward-Extras.md#buying-a-reward-for-a-sibling) |

### `taskmate.approve_reward`
Approve a pending reward claim. For wallet rewards, deducts cost from the child's balance. For pool rewards, clears the allocation (points were already deducted at deposit time).

| Field | Required | Description |
| --- | --- | --- |
| `claim_id` | ✅ | ID of the pending reward claim |

### `taskmate.mark_reward_delivered`
(v7.1.0) An approved reward has been handed over, so it leaves the owed list. See [Reward Fulfilment](Reward-Fulfilment.md).

| Field | Required | Description |
| --- | --- | --- |
| `claim_id` | ✅ | The approved reward claim (from `owed_rewards` on `sensor.taskmate_pending_approvals`) |
| `child_id` | ❌ | Give it when the child is confirming their own reward: the call then goes through the linked-child check and the claim must be theirs. Leave it out for a parent action |

Refused for a claim that is not owed, or already marked delivered.

### `taskmate.start_boost`
(v7.1.0) Open a [boost window](Boost-Windows.md): chores done inside it pay the multiplier. Parent action.

| Field | Required | Description |
| --- | --- | --- |
| `multiplier` | ✅ | 1.1 to 5, e.g. `2` for double |
| `minutes` | ✅ | 1 to 1440 |
| `chore_ids` | ❌ | The chores it covers. Empty or left out = all chores |
| `child_ids` | ❌ | The children it covers. Empty or left out = everyone |
| `starts_at` | ❌ | Start later instead of now, up to a week ahead |
| `name` | ❌ | Label shown on the cards, up to 60 characters |
| `notify` | ❌ | Send the *Boost started* push (default `true`; only when that notification is switched on) |

### `taskmate.end_boost`
(v7.1.0) End a boost early, call off a scheduled one, or skip today's recurring one. Parent action.

| Field | Required | Description |
| --- | --- | --- |
| `boost_id` | ✅ | From the `boosts` attribute of `sensor.taskmate_overview` |

### `taskmate.adjust_screen_time`
Add minutes to a child's [screen-time](Screen-Time-Bank.md) balance, or take some away. Parent action.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | The child |
| `minutes` | ✅ | −10080 to 10080; negative takes minutes away. The balance never goes below zero |
| `reason` | ❌ | A short note for the balance history, up to 60 characters |

### `taskmate.save_screen_time`
A child moves unused minutes into their [screen-time jar](Screen-Time-Bank.md#weekend-jar). Today's allowance goes in first, then banked minutes, up to the jar's cap. Linked-child check, like `complete_chore`. Needs the jar switched on.
### `taskmate.sibling_check`
A child checks a sibling's chore that is waiting for approval. See [Sibling Checks](Sibling-Checks.md). Linked-child check on the **checker**, like `complete_chore`; TaskMate also checks the checker may check that child and isn't checking their own chore.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | The child doing the checking |
| `completion_id` | ✅ | From the checker's `sibling_checks` list on `sensor.taskmate_overview` |
| `verdict` | ✅ | `done` approves it and pays the checker the bonus; `not_yet` leaves it waiting for a parent |
| `note` | ❌ | With `not_yet`, up to 120 characters for the parent |

### `taskmate.set_chore_reminder`
A child picks when to be reminded about one of their chores. See [Child-Chosen Reminders](Child-Chosen-Reminders.md). Linked-child check, like `complete_chore`.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | The child |
| `minutes` | ❌ | How many to save; leave out to save everything that fits |

### `taskmate.rate_reward`
The child gives a reward they've had 1 to 3 stars, once it's been handed over (or approved, when [reward fulfilment](Reward-Fulfilment.md) is off), for three days. Once only. See [Rate the reward](Reward-Extras.md#rate-the-reward). Linked-child check, like `complete_chore`.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | The child who had the reward (for a gift, the recipient) |
| `claim_id` | ✅ | From the child's `rate_rewards` list on `sensor.taskmate_overview` |
| `stars` | ✅ | 1 to 3 |
| `chore_id` | ✅ | One of the child's chores |
| `time` | ❌ | `HH:MM` inside the earliest/latest times in Settings. Empty or left out clears the reminder |

### `taskmate.appeal`
(v7.1.0) A child asks for a second look at a rejection or penalty from the last 48 hours. See [Appeals](Appeals.md). Linked-child check, like `complete_chore`.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | The child appealing |
| `kind` | ✅ | `chore`, `reward` or `penalty` |
| `target_id` | ✅ | From the child's `appealable` list on `sensor.taskmate_overview` |
| `message` | ❌ | Up to 200 characters |

### `taskmate.decide_appeal`
(v7.1.0) Overturn or uphold an appeal. Parent action.

| Field | Required | Description |
| --- | --- | --- |
| `appeal_id` | ✅ | The appeal |
| `overturn` | ✅ | `true` pays the chore, approves the reward or undoes the penalty; `false` lets the decision stand |
| `note` | ❌ | For the child, up to 200 characters |

### `taskmate.reject_reward`
Reject a pending reward claim. For wallet rewards, no action (points were never deducted). For pool rewards, allocation stays in place — child can Redeem again.

| Field | Required | Description |
| --- | --- | --- |
| `claim_id` | ✅ | ID of the pending reward claim |
| `reason` | ❌ | (v6.0.0) Why the claim was turned down, up to 200 characters. Shown to the child and included in the `taskmate_reward_rejected` event. See [Reject Reasons](Reject-Reasons.md). |

### `taskmate.allocate_points_to_pool` (v3.0+)
Move points from a child's spendable balance into a specific reward's pool.

Allocations are **locked** — there is no matching withdraw service. The requested amount is silently capped at whichever is lowest:
- The requested `points`
- The child's current spendable balance
- The pool's remaining capacity (`reward.cost − already_allocated`)

Logs a negative `PointsTransaction` for audit.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | ID of the child making the deposit |
| `reward_id` | ✅ | ID of the reward pool |
| `points` | ✅ | Points to allocate (integer ≥ 1) |

**Example:**
```yaml
service: taskmate.allocate_points_to_pool
data:
  child_id: 8a3b2c1d4e5f6789
  reward_id: 1f2e3d4c5b6a7890
  points: 5
```

**Errors:**
- `ValueError: No spendable points available` — child has no uncommitted points
- `ValueError: Pool for reward 'X' is already full`
- `ValueError: Points to allocate must be at least 1`

## Points services

### `taskmate.add_points`
Add bonus points to a child.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | ID of the child |
| `points` | ✅ | Points to add |
| `reason` |  | Optional reason logged to activity |

### `taskmate.remove_points`
Remove points from a child.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | ID of the child |
| `points` | ✅ | Points to remove |
| `reason` |  | Optional reason |

### `taskmate.gift_points` (v4.0.0)
Transfer spendable points from one child to another (parent-controlled). See [Gifting Points](Gifting-Points.md).

| Field | Required | Description |
| --- | --- | --- |
| `from_child_id` | ✅ | ID of the sending child |
| `to_child_id` | ✅ | ID of the receiving child |
| `points` | ✅ | Points to transfer (integer ≥ 1) |

```yaml
service: taskmate.gift_points
data:
  from_child_id: ef19c56175c14bd9
  to_child_id: 8a3b2c1d4e5f6789
  points: 10
```

Deducts from the sender's spendable balance and credits the recipient. Logs a `PointsTransaction` on both children (`Gift to <name>` / `Gift from <name>`). The gift does **not** count toward the recipient's `total_points_earned` or career score, and the spending cap does not apply. Sender and recipient must differ, and the sender must hold at least `points`. See [Gifting Points](Gifting-Points.md).

### `taskmate.undo_transaction` (v4.0.0)
Reverse a reversible points transaction by its ID — penalties, bonuses, manual add/remove adjustments, and gifts (both legs). Automatic transactions (weekend/streak/perfect-week bonuses, pool moves, decay, interest) cannot be undone. See [Points Economy](Points-Economy.md).

| Field | Required | Description |
| --- | --- | --- |
| `transaction_id` | ✅ | ID of the points transaction to reverse (from the activity feed / `recent_transactions`) |

```yaml
service: taskmate.undo_transaction
data:
  transaction_id: 3f2e1d0c9b8a7654
```

Re-credits (for a penalty) or re-debits (for a bonus) the original amount and removes the transaction record. Undoing a gift reverses both legs (sender re-credited, recipient re-debited). See [Points Economy](Points-Economy.md).

### `taskmate.undo_chore_approval` (v4.1.0)
Reverse an accidental chore approval — removes the awarded points and returns the completion to pending so it can be approved (or rejected) again. See [Points Economy](Points-Economy.md).

| Field | Required | Description |
| --- | --- | --- |
| `completion_id` | ✅ | ID of the approved chore completion to revert to pending |

```yaml
service: taskmate.undo_chore_approval
data:
  completion_id: 9c8b7a6d5e4f3210
```

Removes the points credited at approval, reverses the associated `PointsTransaction`, and moves the completion back into the pending-approvals queue. See [Points Economy](Points-Economy.md).

### `taskmate.record_allowance_payout` (v4.4.0)
Convert a child's points into a real-money allowance payout — deducts the points and records the payout in the allowance ledger at the configured fixed conversion rate. Parent-controlled and audit-logged. See [Allowance](Allowance.md).

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | ID of the child |
| `points` | ✅ | Points to convert to cash and deduct (1–100000) |

```yaml
service: taskmate.record_allowance_payout
data:
  child_id: ef19c56175c14bd9
  points: 100
```

Deducts `points` from the child (logging a `Allowance payout` `PointsTransaction`) and appends a ledger entry recording the cash `amount` (`points ÷ allowance_rate`, rounded to 2 dp) and `currency`. Requires [Allowance](Allowance.md) to be enabled (`allowance_enabled`); raises an error otherwise. Fires the `taskmate_allowance_paid` event. See [Allowance](Allowance.md).

### `taskmate.adjust_streak_freezes` (v6.0.0)
Give a child [streak freeze](Streak-Freezes.md) tokens, or take some away. Parent only.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | ID of the child |
| `amount` | ✅ | Tokens to add (positive) or remove (negative), −10 to 10 |

```yaml
service: taskmate.adjust_streak_freezes
data:
  child_id: ef19c56175c14bd9
  amount: 1
```

A grant never takes the child past **Max streak freezes**, and a removal never goes below zero. Granting is refused while streak freezes are switched off (max set to `0`).

## Penalty services

### `taskmate.add_penalty`
Create a reusable penalty definition.

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `name` | ✅ | — | Penalty name |
| `points` | ✅ | — | Points to deduct when applied (1–10000) |
| `description` | | `""` | Optional description |
| `icon` | | `mdi:alert-circle-outline` | MDI icon |
| `assigned_to` | | all children | List of child IDs this penalty applies to |

### `taskmate.update_penalty`
Update an existing penalty. Only supplied fields are changed.

| Field | Required | Description |
| --- | --- | --- |
| `penalty_id` | ✅ | ID of the penalty to update |
| `name` | | New name |
| `points` | | New points value (1–10000) |
| `description` | | New description |
| `icon` | | New MDI icon |
| `assigned_to` | | New child ID list |

### `taskmate.remove_penalty`
Delete a penalty definition.

| Field | Required | Description |
| --- | --- | --- |
| `penalty_id` | ✅ | ID of the penalty to remove |

### `taskmate.apply_penalty`
Apply a penalty to a child — deducts points and logs a `PointsTransaction` to the activity feed.

| Field | Required | Description |
| --- | --- | --- |
| `penalty_id` | ✅ | ID of the penalty to apply |
| `child_id` | ✅ | ID of the child |

> **Note:** A child's balance can go negative when a penalty is applied.

## Mandatory chore review services (v4.2.0)

When a [mandatory chore](Mandatory-Chores.md) is left incomplete and its time-period window closes, TaskMate records a **mandatory-miss** review item (one per chore/child/day). These services resolve a pending miss; each clears the review item. Find the `miss_id` in the `mandatory_misses` list on [`sensor.taskmate_pending_approvals`](Sensor-Reference.md#sensortaskmate_pending_approvals). See [Mandatory Chores](Mandatory-Chores.md).

### `taskmate.apply_mandatory_penalty`
Deduct the configured penalty points for a missed mandatory chore and clear the review item.

| Field | Required | Description |
| --- | --- | --- |
| `miss_id` | ✅ | ID of the mandatory-miss review item |

```yaml
service: taskmate.apply_mandatory_penalty
data:
  miss_id: 4d3c2b1a0f9e8d7c
```

Deducts the miss's snapshotted `penalty_points` from the child (logging a `PointsTransaction`) when greater than 0, then removes the review item. See [Mandatory Chores](Mandatory-Chores.md).

### `taskmate.postpone_mandatory_chore`
Give a missed mandatory chore another period (or tomorrow) without a penalty, and clear the review item.

| Field | Required | Description |
| --- | --- | --- |
| `miss_id` | ✅ | ID of the mandatory-miss review item |

```yaml
service: taskmate.postpone_mandatory_chore
data:
  miss_id: 4d3c2b1a0f9e8d7c
```

Re-opens the chore in the next remaining time period today; if no window is left today, normal scheduling resurfaces it tomorrow. No points are deducted. See [Mandatory Chores](Mandatory-Chores.md).

### `taskmate.dismiss_mandatory_chore`
Clear a missed mandatory chore review item with no penalty.

| Field | Required | Description |
| --- | --- | --- |
| `miss_id` | ✅ | ID of the mandatory-miss review item |

```yaml
service: taskmate.dismiss_mandatory_chore
data:
  miss_id: 4d3c2b1a0f9e8d7c
```

Removes the review item outright — no points change, no rescheduling. See [Mandatory Chores](Mandatory-Chores.md).

## Bonus services

### `taskmate.add_bonus`
Create a reusable bonus definition.

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `name` | ✅ | — | Bonus name |
| `points` | ✅ | — | Points to award when applied (1–10000) |
| `description` | | `""` | Optional description |
| `icon` | | `mdi:star-circle-outline` | MDI icon |
| `assigned_to` | | all children | List of child IDs this bonus applies to |

### `taskmate.update_bonus`
Update an existing bonus. Only supplied fields are changed.

| Field | Required | Description |
| --- | --- | --- |
| `bonus_id` | ✅ | ID of the bonus to update |
| `name` | | New name |
| `points` | | New points value (1–10000) |
| `description` | | New description |
| `icon` | | New MDI icon |
| `assigned_to` | | New child ID list |

### `taskmate.remove_bonus`
Delete a bonus definition.

| Field | Required | Description |
| --- | --- | --- |
| `bonus_id` | ✅ | ID of the bonus to remove |

### `taskmate.apply_bonus`
Apply a bonus to a child — awards points and logs a `PointsTransaction` to the activity feed.

| Field | Required | Description |
| --- | --- | --- |
| `bonus_id` | ✅ | ID of the bonus to apply |
| `child_id` | ✅ | ID of the child |

## Badge services

### `taskmate.add_badge`
Create a custom badge with optional criteria and point bonus.

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `name` | ✅ | — | Badge display name |
| `description` | | `""` | Description text |
| `icon` | | `mdi:medal` | MDI icon |
| `tier` | | `bronze` | `bronze`, `silver`, `gold`, or `platinum` |
| `point_bonus` | | `0` | Bonus points awarded when earned |
| `criteria` | | `[]` | List of `{metric, operator, value}` objects — AND-evaluated |
| `assigned_to` | | all children | List of child IDs (empty = all) |
| `notify_on_earn` | | `true` | Fire notifications when earned |
| `combinator` |  | How criteria combine — `AND` (all must pass, default) or `OR` (any). See [Achievement Badges](Achievement-Badges.md) |

```yaml
service: taskmate.add_badge
data:
  name: "Super Reader"
  description: "Complete 50 chores and maintain a 7-day streak"
  icon: mdi:book-open-variant
  tier: gold
  point_bonus: 25
  criteria:
    - { metric: total_chores, operator: ">=", value: 50 }
    - { metric: current_streak, operator: ">=", value: 7 }
```

### `taskmate.update_badge`
Update an existing badge. Only supplied fields are changed. Built-in badges allow editing `point_bonus`, `tier`, `assigned_to`, `notify_on_earn`, and `enabled` — criteria, name, description, and icon are frozen.

| Field | Required | Description |
| --- | --- | --- |
| `badge_id` | ✅ | ID of the badge to update |
| `name` | | New name (custom only) |
| `description` | | New description (custom only) |
| `icon` | | New icon (custom only) |
| `tier` | | New tier |
| `point_bonus` | | New point bonus |
| `criteria` | | New criteria list (custom only) |
| `assigned_to` | | New child ID list |
| `notify_on_earn` | | New notification setting |
| `combinator` |  | How criteria combine — `AND` (all must pass, default) or `OR` (any). See [Achievement Badges](Achievement-Badges.md) |

### `taskmate.remove_badge`
Delete a custom badge. Built-in badges cannot be removed — disable them via `update_badge` instead.

| Field | Required | Description |
| --- | --- | --- |
| `badge_id` | ✅ | ID of the badge to remove |

### `taskmate.award_badge_manually`
Manually award a badge to a child, bypassing criteria evaluation. Credits point bonus and fires notification if `notify_on_earn` is true.

| Field | Required | Description |
| --- | --- | --- |
| `badge_id` | ✅ | ID of the badge to award |
| `child_id` | ✅ | ID of the child |

### `taskmate.revoke_badge`
Revoke a previously awarded badge. Automatically reverses any point bonus that was credited.

| Field | Required | Description |
| --- | --- | --- |
| `awarded_badge_id` | ✅ | ID of the awarded badge record (from the admin panel's Award History tab or the badge sensor's `earned` array) |

### `taskmate.rebuild_badges`
Re-evaluate all badges across all children silently. Awards any newly-qualifying badges without notifications or point bonuses. No parameters.

See [Achievement Badges](Achievement-Badges.md) for full details.

## Bounty services (v6.0.0)

One-off jobs on the [Bounty Board](Bounty-Board.md). Posting, editing and removing are parent actions; claiming, giving back and completing are done by the child (or a parent on their behalf). A finished bounty goes through the normal approval queue, so approve or reject it with `approve_chore` / `reject_chore` using its completion ID.

### `taskmate.post_bounty`
Post a job to the board for a fixed number of points.

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `title` | ✅ | — | What the job is, e.g. "Wash the car" (up to 120 characters) |
| `points` | ✅ | — | Points paid when a parent approves the finished job (1–100000) |
| `description` |  | — | Extra detail for the children (up to 500 characters) |
| `icon` |  | — | MDI icon shown on the board |
| `expires_at` |  | — | Date and time the bounty leaves the board if nobody has claimed it. Leave empty for no expiry |
| `eligible_child_ids` |  | all | IDs of the children who may claim it. Empty = every child |
| `claim_hours` |  | `2` | How long a claim lasts (1–48 hours) before the bounty goes back on the board |
| `require_photo` |  | `false` | The child must attach a photo when marking it done |
| `notify_children` |  | `true` | Send the **Bounty posted** notification to the eligible children (the notification type must also be switched on) |

```yaml
service: taskmate.post_bounty
data:
  title: Wash the car
  points: 50
  claim_hours: 3
  require_photo: true
```

### `taskmate.update_bounty`
Edit a bounty. Takes `bounty_id` plus any of the `post_bounty` fields. Once a bounty has been claimed, only its `points` and `expires_at` can change.

### `taskmate.remove_bounty`
Take a bounty off the board.

| Field | Required | Description |
| --- | --- | --- |
| `bounty_id` | ✅ | ID of the bounty |

Not allowed while a finished job is waiting for approval — approve or reject it first.

### `taskmate.claim_bounty`
Claim a bounty for a child, locking it to them for its claim period.

| Field | Required | Description |
| --- | --- | --- |
| `bounty_id` | ✅ | ID of the bounty |
| `child_id` | ✅ | ID of the child claiming it |

A child can hold **one** claim at a time, and only bounties they are eligible for.

### `taskmate.give_back_bounty`
Hand a claimed bounty back to the board so another child can take it. Same fields as `claim_bounty`.

### `taskmate.complete_bounty`
Mark a claimed bounty as done. It goes to the approval queue like a chore.

| Field | Required | Description |
| --- | --- | --- |
| `bounty_id` | ✅ | ID of the claimed bounty |
| `child_id` | ✅ | ID of the child who claimed it |
| `photo_url` |  | Photo of the finished job — required when the bounty asks for one |

Rejecting a finished bounty gives it back to the same child with a fresh claim lock, so they can put it right.

## Wishlist services (v6.0.0)

Services behind the [Wishlist](Wishlist.md). A child adds, saves towards and redeems their own wishes; approving, declining, pledging and removing are parent actions.

### `taskmate.add_wish`
A child adds something they want. It waits for a parent to approve it.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | ID of the child making the wish |
| `name` | ✅ | What the child wants |
| `target` | ✅ | Suggested points it costs (1–100000). The parent can change it when approving |
| `link` |  | A web address (http or https) for the thing |
| `photo_url` |  | A picture just uploaded through TaskMate's photo upload |

A child can have up to **5** wishes on the go at once.

### `taskmate.withdraw_wish`
A child takes back a wish that is still waiting for approval, or clears one that was declined.

| Field | Required | Description |
| --- | --- | --- |
| `wish_id` | ✅ | ID of the wish |
| `child_id` | ✅ | ID of the child whose wish it is |

### `taskmate.move_points_to_wish`
Move points from the child's spendable balance into one of their approved wishes. The points are reserved but still belong to the child.

| Field | Required | Description |
| --- | --- | --- |
| `wish_id` | ✅ | ID of the wish |
| `child_id` | ✅ | ID of the child whose wish it is |
| `points` | ✅ | How many points to move. Capped at the child's balance and at what the wish still needs |

### `taskmate.take_points_from_wish`
Give some of the child's own saved points back to their balance. Same fields as `move_points_to_wish`. Capped at what the child saved; pledged points never come out.

### `taskmate.request_wish_redeem`
Ask to redeem a fully funded wish. It becomes a normal reward claim waiting for a parent's approval (approve or reject it with `approve_reward` / `reject_reward`).

| Field | Required | Description |
| --- | --- | --- |
| `wish_id` | ✅ | ID of the wish |
| `child_id` | ✅ | ID of the child whose wish it is |

### `taskmate.approve_wish`
Turn a waiting wish into a savings goal.

| Field | Required | Description |
| --- | --- | --- |
| `wish_id` | ✅ | ID of the wish |
| `target` |  | Points the wish costs. Leave empty to keep the child's suggestion |

### `taskmate.decline_wish`
Say no to a wish. Any saved points go back to the child and pledges are cancelled.

| Field | Required | Description |
| --- | --- | --- |
| `wish_id` | ✅ | ID of the wish |
| `reason` |  | A reason shown to the child |

### `taskmate.pledge_to_wish`
Record points a relative chips in towards a child's wish. Pledges never touch anyone's balance; they show as a separate stripe on the wish's progress bar.

| Field | Required | Description |
| --- | --- | --- |
| `wish_id` | ✅ | ID of the wish |
| `name` | ✅ | Who the pledge is from, e.g. "Grandma" |
| `points` | ✅ | How many points to pledge. Capped at what the wish still needs |
| `message` |  | A message for the child |

```yaml
service: taskmate.pledge_to_wish
data:
  wish_id: 3c9e2f71a0b84d55
  name: Grandma
  points: 60
  message: Happy saving!
```

### `taskmate.remove_wish_pledge`
Undo a pledge. Allowed until the wish is redeemed.

| Field | Required | Description |
| --- | --- | --- |
| `wish_id` | ✅ | ID of the wish |
| `pledge_id` | ✅ | ID of the pledge |

### `taskmate.remove_wish`
Delete a wish. Saved points go back to the child and pledges are cancelled.

| Field | Required | Description |
| --- | --- | --- |
| `wish_id` | ✅ | ID of the wish |

## Inspection services (v6.0.0)

Parent actions for [Surprise Inspections](Surprise-Inspections.md).

### `taskmate.start_inspection`
Flag a chore approved in the last 24 hours for a spot check.

| Field | Required | Description |
| --- | --- | --- |
| `completion_id` | ✅ | ID of the approved chore completion |
| `bonus` |  | Points paid if it passes (0–10000). Defaults to the Settings value |
| `window` |  | How long you have to check it: `1h`, `2h`, `4h` or `bed` (until bedtime). Defaults to the Settings value |
| `tell_child` |  | Show "Inspection coming" on the child's card now. Turn off for a secret check. Defaults to the Settings value |

An inspection nobody passes or fails before its window ends closes quietly, with no bonus.

### `taskmate.pass_inspection`
The chore passed. Pays the bonus as a normal points entry and plays a celebration on the child's card.

| Field | Required | Description |
| --- | --- | --- |
| `inspection_id` | ✅ | ID of the open inspection |
| `bonus` |  | Points to pay. Defaults to the bonus set when the inspection started |
| `note` |  | A note shown to the child |

### `taskmate.fail_inspection`
The chore didn't pass. No points are taken away.

| Field | Required | Description |
| --- | --- | --- |
| `inspection_id` | ✅ | ID of the open inspection |
| `redo` |  | Put the chore back on the child's list as not done for today. Defaults to the Settings value. The redo pays nothing extra; the original points stand |
| `note` |  | A note shown to the child (what needs fixing) |

### `taskmate.cancel_inspection`
Call off an open inspection, as if it never started.

| Field | Required | Description |
| --- | --- | --- |
| `inspection_id` | ✅ | ID of the open inspection |

## Family services (v7.0.0)

A child's account may make at most 120 child-facing service calls a minute; a burst beyond that is refused ("Too many requests from this account") and recorded in the audit log. Parents, admins and automations are not limited.

Services for the v7.0.0 family features. The ones a child can use for themselves (`request_help`, `log_mood`, `set_weekly_goal`, `buy_raffle_tickets`, `adopt_pet`) go through the same linked-child check as `complete_chore`, so a child's account can only act for that child. `answer_help`, `set_sick_day` and `draw_raffle` are parent actions (an HA admin or a [TaskMate parent](Parent-Access.md); automations are allowed).

### `taskmate.request_help`
A child says they are stuck on a chore. Sends the parents a push; nothing is completed or skipped. See [Help Requests](Help-Requests.md).

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | The child asking for help |
| `chore_id` | ✅ | The chore they are stuck on |
| `message` |  | Optional words from the child, e.g. "I can't reach the shelf" (up to 120 characters) |

```yaml
service: taskmate.request_help
data:
  child_id: ef19c56175c14bd9
  chore_id: 8a3b2c1d4e5f6789
  message: "I can't reach the shelf"
```

A request stays open for two hours, or until a parent answers it. Asking again about the same chore within ten minutes is refused ("Help is already on its way").

### `taskmate.answer_help`
Mark a help request as answered, so the child's card stops saying help is on its way.

| Field | Required | Description |
| --- | --- | --- |
| `request_id` | ✅ | The help request to close. It is in the `request_id` of the `taskmate_help_requested` event, and on the admin panel's Today page |

```yaml
service: taskmate.answer_help
data:
  request_id: 3c9e1a7b5d2f4e60
```

### `taskmate.log_mood`
A child says how their day went. One per day; logging again replaces it. See [Mood Check-In](Mood-Check-In.md).

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | The child |
| `mood` | ✅ | `great`, `good`, `ok`, `sad` or `upset` |

```yaml
service: taskmate.log_mood
data:
  child_id: ef19c56175c14bd9
  mood: good
```

A `sad` or `upset` day can send the parents a gentle push (the `mood_low` notification, off by default). Moods are kept for 90 days.

### `taskmate.set_sick_day`
Give a child a sick day: their chores are hidden, their streak is frozen and no mandatory chore is missed. See [Sick Days](Sick-Days.md).

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `child_id` | ✅ | — | The child who is unwell |
| `date` |  | today | The day, from a week ago to a month ahead |
| `sick` |  | `true` | Set to `false` to take the sick day back |

```yaml
service: taskmate.set_sick_day
data:
  child_id: ef19c56175c14bd9
  sick: true
```

### `taskmate.set_weekly_goal`
Set a child's own weekly points goal. Reaching it pays the family's weekly goal bonus once a week. See [Weekly Goals](Weekly-Goals.md).

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | The child |
| `target` | ✅ | Points to earn this week (0–100000). `0` clears the goal |

```yaml
service: taskmate.set_weekly_goal
data:
  child_id: ef19c56175c14bd9
  target: 120
```

Refused while **Weekly goals** is switched off in Settings. The goal carries over from week to week until it is changed. When a child's own account sets the goal, the target has to be at least the weekly goal bonus and can't change once this week's bonus has been paid; a parent or automation isn't held to either.

### `taskmate.buy_raffle_tickets`
A child spends points on tickets for a raffle. Each ticket is one chance in the draw. See [Raffles](Raffles.md).

| Field | Required | Description |
| --- | --- | --- |
| `raffle_id` | ✅ | The raffle. Find it in the `raffles` attribute of [`sensor.taskmate_rewards`](Sensor-Reference.md) |
| `child_id` | ✅ | The child buying |
| `tickets` | ✅ | How many tickets to buy (1–100) |

```yaml
service: taskmate.buy_raffle_tickets
data:
  raffle_id: 5b7d9f1e3a2c4b68
  child_id: ef19c56175c14bd9
  tickets: 3
```

Refused when the raffle has closed, isn't open to that child, the child can't afford the tickets, or the purchase would take them past the raffle's ticket cap. Raffles themselves are set up, edited and called off from the admin panel's **Raffles** tab; calling one off refunds every ticket.

### `taskmate.draw_raffle`
Draw a raffle's winner now instead of waiting for its draw time.

| Field | Required | Description |
| --- | --- | --- |
| `raffle_id` | ✅ | The raffle to draw |

```yaml
service: taskmate.draw_raffle
data:
  raffle_id: 5b7d9f1e3a2c4b68
```

The winner is picked at random, weighted by tickets. A raffle nobody entered closes with no winner.

### `taskmate.adopt_pet`
A child adopts (or renames) their virtual pet. It grows with every chore they finish from now on. See [Virtual Pets](Virtual-Pets.md).

| Field | Required | Default | Description |
| --- | --- | --- | --- |
| `child_id` | ✅ | — | The child |
| `species` | ✅ | — | `dragon`, `cat`, `dog`, `bunny`, `dino` or `unicorn` |
| `name` | ✅ | — | The pet's name (up to 24 characters) |
| `hatch_egg` |  | `false` | Hatch the egg the grown-up pet laid into a new pet. The old pet joins the pet family |

```yaml
service: taskmate.adopt_pet
data:
  child_id: ef19c56175c14bd9
  species: dragon
  name: Sparky
```

Refused while pets are switched off in Settings. Calling it again for a child who already has a pet renames it (or changes its species) and keeps its growth. `hatch_egg: true` is refused until the pet has laid an egg.

## Miscellaneous

### `taskmate.set_chore_order`
Set the per-child display order of chores.

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | ID of the child |
| `chore_order` | ✅ | Ordered list of chore IDs |

### `taskmate.preview_sound`
Preview a completion sound in the browser. Admin only, like the rest of the sound configuration.

| Field | Required | Description |
| --- | --- | --- |
| `sound` | ✅ | Sound identifier — `none`, `coin`, `levelup`, `fanfare`, `chime`, `powerup`, `undo`, `fart1`–`fart10`, `fart_random` |

### `taskmate.choose_avatar` (v4.0.0)
A child switches to an avatar they have unlocked. See [Avatars](Avatars.md).

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | ID of the child |
| `icon` | ✅ | The MDI icon of an unlocked catalogue avatar (e.g. `mdi:rocket-launch`) |

```yaml
service: taskmate.choose_avatar
data:
  child_id: ef19c56175c14bd9
  icon: mdi:rocket-launch
```

When invoked as a service (child self-service) the avatar must already be unlocked for that child. Parents can assign any catalogue avatar from the [Admin Panel](Admin-Panel.md) regardless of unlock state. See [Avatars](Avatars.md).

### `taskmate.test_notification` (v4.0.0)
Send a sample notification of the given type to its enabled recipients. Ignores the master on/off toggle so routing can be verified.

| Field | Required | Description |
| --- | --- | --- |
| `type_id` | ✅ | Notification type ID, e.g. `pending_chore_approval`, `badge_earned`, `streak_milestone`, `level_up`, `weekly_digest`, `celebration` |

```yaml
service: taskmate.test_notification
data:
  type_id: streak_milestone
```

See [Notifications](Notifications.md) for the full list of notification type IDs.

### `taskmate.read_aloud` (v5.0.0)
Speak a child's outstanding chores to a media player. See [Read Aloud](Read-Aloud.md).

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | ID of the child |
| `media_player` | | Media player to speak on. Falls back to the Settings default. |
| `tts_entity` | | TTS engine to use. Falls back to Settings, then to the only one installed. |
| `message` | | Speak this instead of the generated chore summary. |

```yaml
service: taskmate.read_aloud
data:
  child_id: ef19c56175c14bd9
  media_player: media_player.kitchen
```

The wording comes from parent-editable templates in Settings, not from TaskMate's translations. See [Read Aloud](Read-Aloud.md) for the placeholders.

### `taskmate.spin_roulette` (v5.0.0)
Spin the chore roulette for a child: picks a random outstanding chore and applies a multiplier to it. See [Chore Roulette](Chore-Roulette.md).

| Field | Required | Description |
| --- | --- | --- |
| `child_id` | ✅ | ID of the child |

```yaml
service: taskmate.spin_roulette
data:
  child_id: ef19c56175c14bd9
```

Roulette must be enabled in Settings. Only chores the child can actually do right now are eligible, and the daily spin allowance is enforced.

## Service Side Effects

Several services trigger additional actions beyond their primary purpose:

### `approve_chore`
- Uses the `points` override as the base when one is given (v5.7.0) — every multiplier below still applies on top
- Applies the **quality rating** multiplier when a `rating` is given and [quality ratings](Quality-Ratings.md) are on (v6.0.0)
- Applies the **birthday multiplier** on the child's birthday (v6.0.0, see [Birthday Mode](Birthday-Mode.md))
- Applies the **difficulty multiplier** to the base points (`easy` ×0.5, `medium` ×1.0, `hard` ×2.0 by default — see [Difficulty Tiers](Difficulty-Tiers.md))
- Applies the **weekend multiplier** if the current day is Saturday or Sunday (see [Bonus Points](Bonus-Points.md))
- Applies **time incentives** when the chore sets `due_time` — `+early_bonus` if completed at/before it, `−late_penalty` if after
- Checks and awards **streak milestone bonuses** if the child hits a configured milestone
- Records the child as a **perfect week candidate** (checked Monday at midnight)
- Updates the child's **current streak** and **best streak**
- Advances **levels/XP** (`total_points_earned` is the XP pool) and fires a **level-up celebration** when a threshold is crossed — see [Levels and XP](Levels-and-XP.md) and [Celebrations](Celebrations.md)
- Advances any matching **quests** and **challenges** — see [Quests](Quests.md) and [Challenges](Challenges.md)
- May fire a **celebration** (e.g. all chores done) — see [Celebrations](Celebrations.md)
- Creates a `PointsTransaction` audit record
- Sends a **notification** (persistent + optional push) if a notify service is configured

### `reject_chore`
- **Decrements** the child's current streak by 1 (does not reset to 0)
- Does not award any points
- Stores the optional `reason` and shows it on the child's card for 24 hours (v6.0.0)
- For a finished **bounty**, hands the bounty back to the same child with a fresh claim lock (v6.0.0)

### `approve_reward`
- For **wallet rewards**: deducts cost from the child's balance
- For **pool rewards**: clears the child's allocation (points were already deducted at deposit time)
- For **jackpot pool rewards**: each contributing child loses only their own deposited share
- Decrements the reward's **quantity** by 1 (if limited stock)

### `claim_reward`
- Sends a **notification** (persistent + optional push) for pending reward claims
- For **wallet rewards**: child's balance must cover the cost
- For **pool rewards**: child's allocation must equal or exceed the cost
- Blocked if the reward is **sold out** or **expired**

### `apply_penalty` / `apply_bonus`
- Creates a `PointsTransaction` record logged to the activity feed
- Penalty applications show with a red shield icon in the Activity Card
- Updates the child's `career_score` (`total_points_earned − total_penalties_received`)

### `allocate_points_to_pool`
- Immediately deducts points from the child's spendable balance
- Creates a negative `PointsTransaction` for audit
- Amount is silently capped at the lowest of: requested points, spendable balance, pool remaining capacity

## Complete Service List

The full set of `taskmate.*` services registered by the integration:

`complete_chore`, `complete_bonus_subtask`, `complete_next_chore`, `approve_chore`, `approve_all_chores`, `reject_chore`, `undo_chore`, `leave_team_chore`, `apply_mandatory_penalty`, `postpone_mandatory_chore`, `dismiss_mandatory_chore`, `undo_transaction`, `undo_chore_approval`, `record_allowance_payout`, `test_notification`, `gift_points`, `adjust_streak_freezes`, `request_swap`, `choose_avatar`, `claim_reward`, `approve_reward`, `reject_reward`, `allocate_points_to_pool`, `add_points`, `remove_points`, `preview_sound`, `set_chore_order`, `add_penalty`, `update_penalty`, `remove_penalty`, `apply_penalty`, `add_bonus`, `update_bonus`, `remove_bonus`, `apply_bonus`, `add_chore`, `skip_chore`, `set_chore_manual_start`, `add_task_group`, `update_task_group`, `remove_task_group`, `start_timed_task`, `pause_timed_task`, `stop_timed_task`, `add_badge`, `update_badge`, `remove_badge`, `award_badge_manually`, `revoke_badge`, `rebuild_badges`, `read_aloud`, `spin_roulette`, `post_bounty`, `update_bounty`, `remove_bounty`, `claim_bounty`, `give_back_bounty`, `complete_bounty`, `add_wish`, `withdraw_wish`, `move_points_to_wish`, `take_points_from_wish`, `request_wish_redeem`, `approve_wish`, `decline_wish`, `pledge_to_wish`, `remove_wish_pledge`, `remove_wish`, `start_inspection`, `pass_inspection`, `fail_inspection`, `cancel_inspection`, `request_help`, `answer_help`, `log_mood`, `set_sick_day`, `set_weekly_goal`, `buy_raffle_tickets`, `draw_raffle`, `adopt_pet`.

[Chore auctions](Chore-Auctions.md) have no services: they are run from the admin panel's **Auctions** page and the auction card. Raffles are created, edited and called off from the admin panel's **Raffles** tab; only buying tickets and drawing have services.

## Related

- [Sensor Attributes](Sensor-Attributes.md) — where to find IDs for automations
- [Pool Mode (Savings Jars)](Pool-Mode-(Savings-Jars).md) — feature context for the pool service
- [Gifting Points](Gifting-Points.md), [Chore Swaps](Chore-Swaps.md), [Avatars](Avatars.md), [Difficulty Tiers](Difficulty-Tiers.md), [Photo Proof](Photo-Proof.md) — v4.0.0 feature pages
- [Mandatory Chores](Mandatory-Chores.md) — feature context for the mandatory-miss review services (v4.2.0)
- [Points Economy](Points-Economy.md) — context for the undo services
- [Allowance](Allowance.md) — feature context for the allowance payout service (v4.4.0)
- [Read Aloud](Read-Aloud.md), [Chore Roulette](Chore-Roulette.md) — v5.0.0 feature pages
- [Reactive Chores](Reactive-Chores.md) — `add_chore` with `expires_in_minutes` and `speed_bonus_points`
- [Quality Ratings](Quality-Ratings.md), [Reject Reasons](Reject-Reasons.md), [Child Undo Window](Child-Undo-Window.md), [Teamwork Chores](Teamwork-Chores.md), [Streak Freezes](Streak-Freezes.md), [Watch Complications](Watch-Complications.md) — v6.0.0 changes to chore and points services
- [Bounty Board](Bounty-Board.md), [Wishlist](Wishlist.md), [Surprise Inspections](Surprise-Inspections.md) — v6.0.0 service groups
- [Help Requests](Help-Requests.md), [Mood Check-In](Mood-Check-In.md), [Sick Days](Sick-Days.md), [Weekly Goals](Weekly-Goals.md), [Raffles](Raffles.md), [Virtual Pets](Virtual-Pets.md), [Quantity Chores](Quantity-Chores.md) — v7.0.0 services
