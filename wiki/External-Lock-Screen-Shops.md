# External Lock Screen Shops

Let a separate lock-screen, kiosk, or parental-control system present the shop, while TaskMate stays the authority on points and approvals. The external system submits the child's normal reward claim and waits — it never grants anything itself.

---

## The Rule

**A claim is a request, not a purchase.** Nothing is unlocked and no points move until a parent approves it.

An external shop that unlocks on `taskmate_reward_claimed` has given the child a way to spend points they may not have, on something a parent never agreed to. Wait for `taskmate_reward_approved`.

---

## Reward Event Lifecycle

| Event | Fired when | Correlation fields |
|-------|-----------|-------------------|
| `taskmate_reward_claimed` | A child creates a pending claim | `claim_id`, `child_id`, `reward_id`, `cost` |
| `taskmate_reward_approved` | A parent approves the claim | `claim_id`, `child_id`, `reward_id`, `cost` |
| `taskmate_reward_rejected` | A parent rejects the claim | `claim_id`, `child_id`, `reward_id` |

All three also carry `timestamp`; the approved and rejected events add `child_name` and `reward_name`.

`claim_id` is the same value across all three, so one claim can be followed from request to outcome. Use it to update a pending-purchase indicator and to deduplicate a handler that might see an event twice.

---

## Where The Points Actually Move

Approval is the moment the purchase becomes real, but it is **not** always the moment points leave the child's balance. That depends on how the reward is funded.

| Reward funding | When points leave the child's balance |
|----------------|---------------------------------------|
| Wallet — the normal case | On **approval**. `child.points` drops by the reward's cost. |
| [Pool or jackpot](Pool-Mode-(Savings-Jars).md) with a filled pool | On **allocation**, earlier. Approval only clears the allocation records — the visible balance does not change. |

If your shop tracks balances itself, do not assume `taskmate_reward_approved` means a deduction just happened. Read the child's points sensor after the event rather than subtracting `cost` yourself.

---

## The Safe Pattern

One automation per reward-to-device mapping. Filter **both** the child and the reward, and act only on approval.

```yaml
alias: Release Alex's PC after an approved TaskMate reward
mode: single
triggers:
  - trigger: event
    event_type: taskmate_reward_approved
conditions:
  - condition: template
    value_template: >-
      {{ trigger.event.data.child_id == "alex-child-id"
         and trigger.event.data.reward_id == "pc-time-reward-id" }}
actions:
  - action: switch.turn_off
    target:
      entity_id: switch.alex_pc_blocked
```

Find the ids in **Admin Panel → Children** and **→ Rewards**, or on the `sensor.taskmate_rewards` attributes.

---

## Key Points

- **Keep a single unlock owner.** Use either TaskMate's own [Timed Unlock Rewards](Timed-Unlock-Rewards.md) for a reward *or* an external approval automation — never both on the same reward, or two systems will fight over the same switch.
- **Fail closed.** An unrecognised child or reward id should do nothing. Never fall back to "unlock anyway".
- **Never retry by re-claiming.** If your unlock action fails, leave the claim record alone and alert a parent. Submitting a second claim charges the child twice.
- **Make the action idempotent.** The same approval may reach your handler more than once; turning a switch off twice must be harmless.
- **Filter on ids, not names.** `child_name` and `reward_name` are for display and change whenever a parent renames something.

---

## Correlating Without Events

If you would rather poll than listen to the bus, the same ids are on sensor attributes:

| Source | What it gives you |
|--------|-------------------|
| `sensor.taskmate_pending_approvals` → `reward_claims[]` | Every pending claim, each with `claim_id`, `child_id`, `reward_id`, `cost` |
| `sensor.taskmate_rewards` → `pending_reward_claims[]` | The same pending list, alongside the reward catalogue |
| `sensor.taskmate_activity` → `recent_transactions[]` | Approved claims, where `transaction_id` **is** the claim id and `type` is `reward_approved` |

Two limits make the event bus the better choice for anything that must not be missed:

- **Rejections leave no trace.** A rejected claim is deleted outright, so it never appears in the activity feed. Polling can only see that it vanished from the pending list, and cannot tell you it was rejected rather than approved.
- **The activity feed is capped at 20 entries** to stay under Home Assistant's recorder attribute limit. A busy family can push an approval out of the window before a slow consumer reads it.

---

## Related

- [Rewards](Rewards.md) — costs, jackpots, spending caps and the claim flow
- [Managing Rewards](Managing-Rewards.md) — the parent approval workflow
- [Timed Unlock Rewards](Timed-Unlock-Rewards.md) — TaskMate's own built-in device unlocking
- [Pool Mode (Savings Jars)](Pool-Mode-(Savings-Jars).md) — why approval doesn't always deduct
- [Automations](Automations.md) — every TaskMate bus event
- [Sensor Reference](Sensor-Reference.md) — all entities and their attributes
