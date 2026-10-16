# Timed Unlock Rewards

Spend points to unlock something for a while — the TV, the console socket, a wifi group. Approving the claim turns the entity on; a timer turns it back off.

![The unlock allowlist lives in Settings](images/panel-settings.png)

---

## Two Deliberate Limits

This is the one TaskMate feature that reaches out and changes your house, so it is deliberately narrow:

1. **A reward can only turn one entity on and back off.** There is no free-form service call, no payload, no template.
2. **The entity must be on your allowlist.**

An empty allowlist permits **nothing**. This gates household devices, so the safe default when unconfigured is "no".

---

## Setting It Up

**1. Settings → Unlock allowlist**

Add the entities a reward may touch. An entry can be:

- a full entity id — `switch.xbox`
- a bare domain — `switch`, to permit everything in it

**2. Open a reward → Advanced — timed unlock**

Pick an allowlisted entity and a duration, up to 24 hours. `0` leaves it on for you to turn off yourself.

---

## Key Points

- **The allowlist is checked twice** — when the reward is saved, and again when it fires. You can revoke an entity later and any reward pointing at it quietly stops unlocking rather than breaking.
- **Active unlocks are persisted.** A Home Assistant restart mid-unlock re-arms the timer; anything already past due is turned off at startup. A restart can never strand the television on.
- **Turning something off is never gated by the allowlist.** A revert is always safe, so removing an entity from the allowlist can't trap it in the on state.

---

## Events

| Event | Fired when |
|-------|-----------|
| `taskmate_unlock_started` | The unlock begins |
| `taskmate_unlock_ended` | The timer reverts it |

Both carry `entity_id`, `reward_id`, `reward_name`, `child_id`, `child_name`, `started_at` and `revert_at`.

---

## Examples

| Reward | Entity | Duration |
|--------|--------|----------|
| One hour of Xbox | `switch.xbox_socket` | 60 min |
| Film night | `switch.living_room_tv` | 180 min |
| Extra wifi after bedtime | `switch.kids_wifi` | 30 min |

---

## Related

- [Rewards](Rewards.md) — costs, jackpots, spending caps and the claim flow
- [Managing Rewards](Managing-Rewards.md) — the parent approval workflow
- [Settings](Settings.md) — the unlock allowlist
- [Insights](Insights.md) — the health report flags a reward whose entity has left the allowlist
- [Automations](Automations.md) — every TaskMate bus event
