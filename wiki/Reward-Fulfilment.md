# Reward Fulfilment

Approving a reward spends the child's points. Until now that was the end of the story: nothing recorded whether the movie night actually happened or the Lego set ever arrived. **Reward fulfilment** keeps every approved reward on an **owed** list until somebody hands it over, shows the child what they are still due, and nags the parents when something has sat there too long.

> **New in v7.1.0**

---

## Turning It On

**TaskMate panel → Settings → Reward fulfilment**

| Setting | Key | Default | Description |
|---------|-----|---------|-------------|
| **Track rewards until they are handed over** | `reward_fulfilment_enabled` | off | Approved rewards go on the owed list instead of disappearing into history |
| **Remind me after** | `reward_fulfilment_reminder_days` | `3` | Days before parents get a push saying a reward is still owed, repeated every that many days while it stays owed. `0` = never remind (0–60) |

Only rewards approved **while the tracker is on** are tracked. Turning it on does not back-fill old purchases, and turning it off hides the list without deleting anything.

### What is never tracked

- **Streak freezes** — TaskMate hands the token over itself the moment the claim is approved
- **Timed unlocks** — the entity switches on by itself (see [Timed Unlock Rewards](Timed-Unlock-Rewards.md))
- **Wishlist redemptions** — a [wish](Wishlist.md) already has its own hand-over step

---

## Handing a Reward Over

Anywhere a parent approves rewards, the owed ones sit underneath with a **Handed over** button:

- **Approvals card** — a *Still to hand over* section after the pending items, in every design style. Owed rewards never count towards the card's pending badge; they are not approvals.
- **Admin panel → Today** — a *Rewards to hand over* card beside *Asked for help*, following the child filter.

The child can also confirm for themselves: their card shows **You're owed a reward** with the reward, how long ago it was redeemed and a **Got it!** button. Tapping it marks the reward delivered by the child.

Marking a reward delivered is final; there is no "un-deliver". If a parent taps by mistake, nothing is lost: the purchase is still in history, it just leaves the owed list.

---

## Reminders

With the reminder set to *N* days, the parents receive the **Reward still owed** push the first time a reward has been owed for *N* days, then again every *N* days until it is handed over:

> 🎁 Malia is still waiting for 'Movie night' — redeemed 3 days ago.

The notification type `reward_owed` is **on by default** because it only ever fires once a parent has switched the tracker on. Route it or switch it off on the Notifications tab like any other type. It follows [multi-parent routing](Multi-Parent-Approval-Routing.md).

---

## Service

| Service | Fields | Description |
|---------|--------|-------------|
| `taskmate.mark_reward_delivered` | `claim_id`, `child_id` (optional) | Mark an owed reward as handed over. Without `child_id` it is a parent action (an HA admin or a [TaskMate parent](Parent-Access.md); automations are allowed). With `child_id` it is the child confirming their own, through the same linked-child check as `complete_chore`, and the claim must belong to that child |

```yaml
action: taskmate.mark_reward_delivered
data:
  claim_id: 9c2f6d1e4a7b8c3d
```

Find the `claim_id` in the `owed_rewards` attribute of `sensor.taskmate_pending_approvals`, or in the `taskmate_reward_approved` event.

---

## Event

Handing a reward over fires `taskmate_reward_delivered` with `child_id`, `child_name`, `reward_id`, `reward_name`, `claim_id`, `delivered_by` (`parent` or `child`) and `timestamp`. It shows as **Reward handed over** on the child's [event entity](Event-Entities.md).

---

## Sensors

| Where | Attribute | Contents |
|-------|-----------|----------|
| `sensor.taskmate_pending_approvals` | `owed_rewards` | Every owed reward, oldest first: `claim_id`, `child_id`, `child_name`, `reward_id`, `reward_name`, `reward_icon`, `cost`, `approved_at`, `days_owed`. Present only while the tracker is on and something is owed |
| `sensor.taskmate_overview` → `children[]` | `owed_rewards` | That child's owed rewards, compact: `claim_id`, `reward_name`, `reward_icon`, `days_owed`. Present only when there is one |

---

## Related

- [Rewards](Rewards.md) — the rewards card and how claims work
- [Managing Rewards](Managing-Rewards.md)
- [Approvals Card](Approvals-Card.md)
- [Notifications](Notifications.md)
