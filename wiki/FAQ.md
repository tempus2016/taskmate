# FAQ

Common questions about TaskMate. If yours isn't answered here, please open an [issue](https://github.com/tempus2016/taskmate/issues).

## General

### Does TaskMate send my data anywhere?
No. TaskMate is fully local-first. All child, chore, reward, and points data is stored inside your Home Assistant instance under `.storage/`. Nothing leaves your network.

### What HA version do I need?
Home Assistant 2024.7 or newer (matches the value in `hacs.json`).

2024.7.0 is where `hass.http.async_register_static_paths` was introduced, which TaskMate uses to serve its dashboard cards. On anything older the integration fails to load rather than degrading. CI tests this floor directly, alongside current HA.

### How do I back up my TaskMate data?
Your normal Home Assistant backups include the `.storage/` directory, which is where TaskMate keeps everything. Nothing extra required.

## Chores

### What's the difference between "specific days" and "recurring" chore modes?
- **Specific days**: show this chore on the selected days of the week (e.g. Monday / Wednesday / Friday).
- **Recurring**: rolling window — show again every 2 days / weekly / every 2 weeks / monthly / every 3 months / every 6 months after the last completion.

### Can I create a chore that only shows once?
Yes — use **one-shot** chores. A one-shot chore is available the day it's created and automatically expires at midnight. Each assigned child has their own chance to complete it.

### Can chores be conditional on a sensor?
Yes. Set `visibility_entity`, `visibility_state`, and `visibility_operator` on a chore. For example: show *"Feed the cat"* only when `binary_sensor.cat_food_bowl` is `off`.

## Rewards

### What happens if a child tries to claim a reward they can't afford?
In wallet mode, the Claim button is disabled and shows *"Not enough points"* on hover. In pool mode, the Redeem button only appears once the pool is full.

### Can I mix wallet rewards and pool rewards on the same card?
Yes — this is the main use case for the per-reward `pool_enabled` toggle. Short-term treats stay as wallet rewards (instant claim); long-term goals become pool rewards (savings jars).

### What happens when I delete a reward?
Any pending claims for it are removed, any pool allocations are cleared (points are not refunded to children), and the reward disappears from every rewards card.

## Pool Mode

### Do I have to use Pool Mode?
No. It's entirely opt-in — both per-reward (admin toggle) and per-card (`enable_pool_mode: true`). Existing v2.x installs continue to work unchanged.

### Can my child move points back out of a pool?
No — by design. Allocated points are locked to teach commitment. If you need to reset a pool as a parent, delete the reward (which clears allocations) and recreate it.

### What happens if I reject a pool-mode claim?
The claim is removed but **the allocation stays full**. The child can hit Redeem again immediately. Rejection in pool mode means *"not this time, ask me again later"*. To permanently cancel a pool, delete the reward.

### Why didn't the LEGO bar move when my child earned 10 points?
In Pool Mode, earning points grows the **spendable balance** (shown at the top of the card). The LEGO bar only grows when the child taps a deposit button for that specific reward.

### How do jackpots work with Pool Mode?
Jackpots are **always pool-mode** (enabling **Is Jackpot** hides the separate Pool toggle). Each assigned child has their own deposit buttons; the combined jackpot pool fills as children contribute. Any assigned child can tap Redeem when it's full; on approval each contributing child loses only their own share. This is how a goal no single child could afford alone gets reached together — combining everyone's points.

### The Claim button on my Rewards Card is missing or won't work
Make sure you're on **v4.2.1 or newer**. Earlier versions only showed a claim button when the card had a `child_id` set. As of v4.2.1 the card shows a **child picker** and defaults to the first child when `child_id` is omitted, so claiming works out of the box. For jackpot rewards you'll see pooled **deposit** buttons rather than a single claim button — that's expected (jackpots combine everyone's points).

### The deposit button says "Select a child to deposit" — why?
The card has no `child_id` set, so TaskMate doesn't know which child is making the deposit. Either set `child_id:` in the card YAML, or use one card per child.

### What are assignment modes?
Assignment modes control how a chore is distributed among assigned children. `everyone` (default) shows it to all children. `alternating` rotates one child per day. `random` picks a random child each day. `balanced` distributes today's chores evenly so no one child gets overloaded.

### Can I publish chores to a calendar?
Yes. On each chore, select one or more HA calendar entities in the **Calendar Entities** field. TaskMate creates all-day events for each assigned child, projected ahead by the configured number of days (default 14, up to 90). Configure the projection horizon in Settings.

### What is the claim allowance?
A grace period (in minutes) after a chore's time window ends during which the child can still complete it. Default: 0 (no grace). Set it on a per-chore basis.

### What is the availability entity on a child?
An optional HA entity (e.g. `binary_sensor` or `input_boolean`) that indicates whether a child is available. When the entity is not in a recognised "available" state, chores with **Require Availability** enabled will skip that child in assignment rotation. You can also set **Availability Inverted** to flip the logic, and add an **Unavailability Entity** as a second busy signal.

## Timed tasks

### What are timed tasks?
Chores where points are earned based on duration rather than a tick-off. Children start, pause, and stop a timer. Points are calculated as `floor(total_seconds / (rate_minutes × 60)) × rate_points`. See [Timed Tasks](Timed-Tasks.md).

### Can I set a daily limit on timed tasks?
Yes — use the **Daily Cap (minutes)** setting on the chore. When the cap is reached, the timer cannot be started again until the next day. Set to `0` for unlimited.

### What happens if a child forgets to stop the timer?
Stale sessions from previous days are automatically stopped and submitted at midnight. A completion record is created with the elapsed time up to that point.

## Task groups

### What are task groups?
Task groups coordinate how rotation-mode chores are assigned together. A **sticky** group assigns all its chores to the same child. A **spread** group assigns each chore to a different child. See [Task Groups](Task-Groups.md).

### Do task groups work with "everyone" mode?
No — groups only affect chores using `alternating`, `random`, or `balanced` assignment modes. Chores in `everyone` mode are shown to all children regardless of groups.

## Bonus subtasks

### What are bonus subtasks?
Optional extra-credit tasks embedded within a parent chore. They unlock after the parent chore is completed and award additional points. See [Bonus Subtasks](Bonus-Subtasks.md).

### Do bonus subtasks count toward streaks?
No — only the parent chore completion affects streak tracking.

## Admin panel

### Where is the admin panel?
It's in the HA sidebar under **TaskMate**. It opens at `/taskmate-admin` and requires an admin HA user. See [Admin Panel](Admin-Panel.md).

### Is there still a config flow for managing chores and rewards?
No. The old options/configure flow was retired in v4.0.0 — the admin panel is the only place to manage children, chores, rewards, groups, settings, notifications, badges and templates. A config flow still runs once when you first add the integration, to set the points name and icon.

## Streaks & bonuses

### What's the difference between "reset" and "pause" streak modes?
- **Reset** (default): miss a day, your streak goes back to 0
- **Pause**: miss a day, your streak is frozen until you complete again, then resumes

### How do perfect week bonuses work?
If a child completes at least one chore on every day of a week (Monday to Sunday), they receive the perfect-week bonus the following Monday at midnight. The bonus amount is configurable in Settings.

### What are streak milestones?
Configurable point bonuses awarded when a streak reaches certain day counts. Default: `3:5, 7:10, 14:20, 30:50, 60:100, 100:200` — meaning +5 points at 3 days, +10 at 7 days, etc. Format is `days:points` CSV.

## Notifications

### Do I get notified when a child does something?
Yes, by default a `persistent_notification` is created for every pending chore approval and (from v3.0) every pending reward claim.

You can also configure a `notify.*` service — typically a mobile notification integration — in TaskMate settings to also send those notifications to your phone.

## Troubleshooting

### The rewards card shows "Entity not found"
Make sure the `entity` config points to an existing sensor. The default is `sensor.taskmate_overview` — check Developer Tools → States to confirm it exists.

### My changes don't show up after updating
Hard-refresh your Lovelace dashboard with `Ctrl/Cmd + Shift + R`. Home Assistant caches frontend assets aggressively.

### Pool allocations aren't deducting from the child's balance
This was a bug in v3.0.0-beta1 — upgrade to v3.0.0 (stable) or later. An automatic migration adjusts existing allocations on first load.

### What is career score?
A long-term performance metric: `total_points_earned − total_penalties_received`. It's tracked per child and snapshotted daily for historical trends.

## Related

- [Managing Rewards](Managing-Rewards.md)
- [Pool Mode (Savings Jars)](Pool-Mode-(Savings-Jars).md)
- [Services](Services.md)
- [Sensor Attributes](Sensor-Attributes.md)
