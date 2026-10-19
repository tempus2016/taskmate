# Managing Rewards

Rewards are the things children earn points toward (movie night, an hour of screen time, a LEGO set…). They're created and edited from the Rewards tab of the TaskMate panel.

![The Rewards tab](images/panel-rewards.png)

## Where to find it

Open the **TaskMate** panel in the Home Assistant sidebar and go to **Rewards**.

The tab lists all existing rewards, with **+ Add reward** to create one.

## Reward form fields

| Field | Required | Description |
| --- | --- | --- |
| **Name** | ✅ | Display name shown on cards |
| **Description** |  | Optional longer text shown under the name |
| **Points cost** | ✅ | Fixed number of points required to earn this reward |
| **Icon** |  | An MDI icon (dropdown picker) |
| **Assigned to** |  | Which children can earn this reward. Leave empty = all children |
| **Is Jackpot** |  | If enabled, pools points from all assigned children toward one shared reward. Jackpots are **always pool-mode**, so the separate Pool Reward toggle is hidden when this is on |
| **Quantity** |  | Limited stock count. Each approved claim decreases it by 1. When it reaches 0 the reward shows as **Sold Out**. Leave empty for unlimited. |
| **Expiration Date** |  | ISO date after which the reward is no longer available. Expired rewards are hidden from claim buttons. Pool allocations for expired rewards are refunded automatically at midnight. Leave empty for no expiry. |
| **Pool Reward (Savings Jar)** |  | If enabled, children deposit points into this reward's dedicated pool rather than spending from their global balance. See below. (Hidden for jackpots, which are always pooled.) |

### Pool Reward toggle (v3.0+)

The **"Pool Reward (Savings Jar)"** switch flips a single reward between two fundamentally different behaviours:

- **Off** (default, wallet mode): Classic behaviour. The child's balance must cover the full cost. Tapping Claim creates a pending claim; approval deducts the cost from the child's balance.
- **On** (pool mode): The reward shows `[+1] [+5] [+10]` deposit buttons. Children deposit points from their spendable balance; each deposit immediately reduces `child.points` and grows the allocation. When the allocation reaches the reward cost, a Redeem button appears.

You can flip the toggle on an existing reward at any time. If you turn it off after deposits have been made, those points stay allocated until the reward is claimed or deleted — there's no auto-refund.

See [Pool Mode (Savings Jars)](Pool-Mode-(Savings-Jars).md) for full semantics.

## Editing an existing reward

Click a reward's **✏** button to edit it. The dialog is identical to the add form but pre-filled, with **Save** to persist changes and **Delete** to remove the reward.

### What happens when you delete a reward

- All pending claims for that reward are removed
- All pool allocations for that reward are cleared (points are **not** refunded to children)
- The reward disappears from every rewards card

If a reward has active pool allocations and you want to cancel it gracefully, this is currently the escape hatch — delete and recreate.

## Auto-restock (v4.0.0)

Limited-stock rewards can refill on a schedule instead of needing a manual top-up. In the reward's Add/Edit form:

1. Set a **Quantity** so the reward has limited stock
2. Turn on **Auto-restock**
3. Set **Restock to** — the number stock is reset to each period
4. Choose **Restock every**: Day, Week (Mon), or Month (1st)

On the chosen boundary TaskMate resets the reward's **Quantity** back to the Restock-to amount, so a reward that sold out becomes available again. See [Rewards](Rewards.md#auto-restock-v400) for the exact mechanics.

## Per-period spending cap (v4.0.0)

The spending cap is **not** set on individual rewards — it is a family-wide control in the **TaskMate** panel → **Settings**, under **History & streaks**:

1. Turn on **Spending cap**
2. Set **Cap (pts)** — the maximum points each child may spend on rewards per period (`0` disables it)
3. Choose the **Period**: weekly (resets Monday) or monthly (resets on the 1st)

Once set, approving a reward claim that would take a child over their cap for the current period is blocked with a "Spending cap reached" error. The claim remains pending, so you can approve it after the period rolls over or reject it. Only approved claims count toward the cap. See [Rewards](Rewards.md#per-period-spending-cap-v400) for the full behaviour.

## Jackpots are always pooled

Enabling **Is Jackpot** automatically puts the reward in pool mode — there's no separate Pool Reward toggle to set (the editor hides it). This is because a jackpot's whole point is combining everyone's points, which only works via the pool. Behaviour:

- The pool total is the sum of all contributing children's allocations
- Each assigned child has their own `[+1] [+5] [+10]` deposit buttons
- Any assigned child can tap Redeem when the combined pool fills
- On approval, each contributing child loses only their own share
- A goal no single child could afford on their own is reached together

## Tips

- **Price rewards so savings takes days, not weeks.** Short feedback loops keep kids engaged.
- **Mix pool and wallet rewards** so kids can satisfy an impulse (10pt candy) while working toward a goal (500pt LEGO).
- **Use jackpots sparingly** — they're powerful for family goals but harder for kids to grok.

## Related

- [Dashboard Cards](Dashboard-Cards.md) — the Rewards card and others
- [Pool Mode (Savings Jars)](Pool-Mode-(Savings-Jars).md) — the savings-jar feature
- [Streak Freezes](Streak-Freezes.md) — a Streak freeze reward gives the child a token that saves their streak
- [Services](Services.md) — programmatic reward operations
