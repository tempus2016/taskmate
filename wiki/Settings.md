# Settings

All TaskMate settings are configured via the **TaskMate** panel → **Settings**.

![The Settings tab](images/panel-settings.png)

---

## Settings Reference

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Points Currency Name** | `Stars` | — | Display name for the points currency (Stars, Coins, Bucks, Tokens, etc.). Shown on all cards and notifications. |
| **Points Currency Icon** | `mdi:star` | Any MDI icon | Icon shown next to point values throughout the UI. Since v6.2.0 the icon and name are used everywhere points appear, including bounties, auctions and every card, instead of a fixed star or "pts". |
| **Weekend Points Multiplier** | `2.0` | 1.0–5.0 | Multiplier applied to chore points on Saturday and Sunday. Set `1.0` to disable. Formula: `weekend_bonus = round(base_points × (multiplier − 1.0))`. The bonus is logged as a separate transaction. |
| **Streak Reset Mode** | `reset` | `reset` / `pause` | What happens when a child misses a day. **Reset**: streak goes back to 0. **Pause**: streak freezes and resumes on the next completion. |
| **Streak Milestone Bonuses** | `on` | on / off | Master toggle for streak milestone point bonuses. |
| **Streak Milestone Configuration** | `3:5, 7:10, 14:20, 30:50, 60:100, 100:200` | `days:points` CSV | Custom milestone thresholds. Each entry awards bonus points when the child's streak reaches that day count. Milestones reset when the streak resets, so they can be re-earned. |
| **Streak needs all tasks** (`streak_requires_all_chores`) | `off` | on / off | When on, a day only extends the streak once **every** chore due that day is done. When off (default), completing any one chore keeps the streak alive. |
| **Perfect Week Bonus** | `on` | on / off | Award bonus points when a child completes at least one chore every day Mon–Sun. Checked Monday at midnight. |
| **Perfect Week Bonus Points** | `50` | 0–1000 | Points awarded per perfect week. |
| **Perfect week needs all tasks** (`perfect_week_requires_all_chores`) | `off` | on / off | When on, a day counts toward a perfect week only when **every** chore due that day is done. When off (default), one completed chore is enough for the day to count. |
| **Notification Service** | *(empty)* | Any `notify.*` service | Optional HA notify service for push notifications on pending chore approvals and reward claims. e.g. `notify.mobile_app_johns_phone`. Leave empty to use persistent notifications only. See [Notifications](Notifications.md). |
| **Calendar projection** (`calendar_projection_days`) | `14` | 1–90 | Days ahead each chore publishes to the per-child calendar entities. Higher values give more planning visibility but create more calendar entries. See [Calendar](Calendar.md). |
| **History Days to Keep** | `90` | 30–365 | Number of days of completion history to retain. Older records are pruned daily at 00:01. |

> **Also available as entities (v4.4.0):** `weekend_multiplier`, `perfect_week_bonus`, `streak_reset_mode`, and `card_design` are additionally surfaced as Home Assistant `number`/`select` entities, so you can read and change them from automations, scripts, and the HA UI without the panel. Panel and entity stay in sync. See [Configuration Entities](Configuration-Entities.md).

### Parents — no admin rights (v4.5.0)

In the Settings tab, the **Parents (no admin rights)** section lists your non-admin Home Assistant users with a checkbox each. Ticking a user grants them the day-to-day TaskMate parent controls (approve/reject chores and rewards, adjust points, confirm allowance, complete-on-behalf, undo) from the cards — **without** Home Assistant admin rights, and without access to this admin panel or any configuration. Stored under `parent_user_ids`; only an admin can change it. See [Parent Access](Parent-Access.md).

### Difficulty Multipliers (v4.0.0)

Each chore carries a difficulty tier; the points it awards are the base points × the tier's multiplier. `medium` is the neutral baseline (×1.0) so chores created before this feature keep their exact award value. See [Difficulty Tiers](Difficulty-Tiers.md). Settings stored under keys `difficulty_multiplier_easy` / `difficulty_multiplier_medium` / `difficulty_multiplier_hard`.

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Easy multiplier** | `0.5` | 0.0–10.0 | Points multiplier applied to `easy` chores |
| **Medium multiplier** | `1.0` | 0.0–10.0 | Baseline multiplier for `medium` chores |
| **Hard multiplier** | `2.0` | 0.0–10.0 | Points multiplier applied to `hard` chores |

### Levels & XP (v4.0.0)

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **XP per Level** (`level_xp_step`) | `100` | 1–100000 | Lifetime points needed to advance one [level](Levels-and-XP.md). `level = (total_points_earned // step) + 1`. |

### Surprise / Random Bonus (v4.0.0)

A daily (16:00) opt-in roll that may award each child a random bonus, fires the `taskmate_surprise_bonus` event. See [Points Economy](Points-Economy.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Surprise Bonus** (`surprise_bonus_enabled`) | `false` (off) | on / off | Master toggle for the random surprise bonus |
| **Surprise chance** (`surprise_bonus_chance`) | `15` | 0–100 | Percent chance per child each day |
| **Surprise min** (`surprise_bonus_min`) | `5` | 0–10000 | Minimum points awarded when it triggers |
| **Surprise max** (`surprise_bonus_max`) | `20` | 0–10000 | Maximum points awarded when it triggers |

### Points Decay (v4.0.0)

Anti-hoarding: periodically decay each child's spendable points. Logs a transaction; does **not** touch career score. See [Points Economy](Points-Economy.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Points Decay** (`points_decay_enabled`) | `false` (off) | on / off | Master toggle |
| **Decay period** (`points_decay_period`) | `monthly` | `weekly` / `monthly` | `weekly` runs Mondays, `monthly` runs on the 1st |
| **Decay percent** (`points_decay_percent`) | `10` | 0–100 | Percent of the balance removed each period |

### Savings Interest (v4.0.0)

Rewards saving: periodically credit interest on each child's spendable balance. Fires `taskmate_interest_paid`. See [Points Economy](Points-Economy.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Savings Interest** (`interest_enabled`) | `false` (off) | on / off | Master toggle |
| **Interest period** (`interest_period`) | `weekly` | `weekly` / `monthly` | `weekly` runs Mondays, `monthly` runs on the 1st |
| **Interest percent** (`interest_percent`) | `5` | 0–100 | Percent of the balance credited each period |

### Reward Spending Cap (v4.0.0)

Limit how many points a child can spend on rewards per period. Enforced at reward approval. See [Points Economy](Points-Economy.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Spending Cap** (`spend_cap_enabled`) | `false` (off) | on / off | Master toggle |
| **Cap period** (`spend_cap_period`) | `weekly` | `weekly` / `monthly` | `weekly` resets Mondays, `monthly` resets on the 1st |
| **Cap amount** (`spend_cap_amount`) | `0` | 0–1000000 | Max points spendable per period (0 = unlimited) |

### Celebrations (v4.0.0)

Optional celebratory notifications for big moments (level-ups, streak milestones, perfect weeks, quest/challenge completions). The `taskmate_celebration` event always fires regardless of these settings; these control whether a **notification** is sent. See [Celebrations](Celebrations.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Celebration notifications** (`celebration_notify`) | `false` (off) | on / off | Send a notification on celebration moments |
| **Minimum celebration tier** (`celebration_notify_min_tier`) | `2` | 1–3 | Only notify for moments at this tier or higher: 1 = small, 2 = medium, 3 = epic |

### Time-of-Day Boundaries (v3.6.0+)

These settings control the time windows used for morning, afternoon, evening, and night chores when publishing to HA calendar entities. Configurable via the [Admin Panel](Admin-Panel.md).

| Setting | Default | Format | Description |
|---------|---------|--------|-------------|
| **Morning Start** | `06:00` | `HH:MM` | Start of the morning time window |
| **Morning End** | `12:00` | `HH:MM` | End of the morning time window |
| **Afternoon Start** | `12:00` | `HH:MM` | Start of the afternoon time window |
| **Afternoon End** | `17:00` | `HH:MM` | End of the afternoon time window |
| **Evening Start** | `17:00` | `HH:MM` | Start of the evening time window |
| **Evening End** | `21:00` | `HH:MM` | End of the evening time window |
| **Night Start** | `21:00` | `HH:MM` | Start of the night time window |
| **Night End** | `23:59` | `HH:MM` | End of the night time window |

Invalid values fall back to the defaults. `anytime` chores are published as all-day calendar events.

### Custom Time-of-Day Periods (v4.0.0)

<a name="time-of-day-periods-v400"></a>

v4.0.0 generalises the four fixed windows above into a fully **customisable period list** (`time_periods`). Each period has an `id`, a `label` (empty = use the built-in translated name), a `start`/`end` in `HH:MM`, and an `icon`. The built-in `morning` / `afternoon` / `evening` / `night` ids ship as the defaults shown above; you can rename them, change their windows, or add up to 24 periods total. The `anytime` category is implicit (all-day, always available) and never appears in the list. The legacy four `*_start`/`*_end` boundary keys are still mirrored on the overview sensor for backward compatibility.

### Card Design (v4.2.0)

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Default card design** (`card_design`) | `classic` | `classic` / `playroom` / `console` / `cleanpro` / `accessible` / `graphite` | The style new cards use unless overridden per card. A selector offering Classic / Playroom / Console / Clean Pro / Accessible / Graphite. Every card left on *Use global default* follows this value. See [Card Design Styles](Card-Design-Styles.md). |

### Allowance (v4.4.0)

Convert points into a real-money allowance. When enabled, parents can record a payout (via [`record_allowance_payout`](Services.md#taskmaterecord_allowance_payout-v440) or the admin panel) that deducts points and logs a ledger entry at the fixed conversion rate. See [Allowance](Allowance.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Allowance enabled** (`allowance_enabled`) | `false` (off) | on / off | Master toggle for the allowance feature |
| **Allowance rate** (`allowance_rate`) | `10` | 1–100000 | Points per one unit of currency. Cash `amount = points ÷ rate`, rounded to 2 dp |
| **Allowance currency** (`allowance_currency`) | *(empty)* | up to 8 chars | Currency label recorded on each payout (e.g. `£`, `USD`) |

### Family Goals (v4.4.0)

A shared co-op goal: when the family's combined points reach the target, TaskMate fires `taskmate_family_goal_reached` and notifies. The achieved flag resets whenever the target or enabled toggle changes. See [Family Goals](Family-Goals.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Family goal enabled** (`family_goal_enabled`) | `false` (off) | on / off | Master toggle for the family co-op goal |
| **Family goal name** (`family_goal_name`) | *(empty)* | up to 120 chars | Display name of the goal |
| **Family goal target** (`family_goal_target`) | `500` | 1–10000000 | Combined points needed to reach the goal |
| **Family goal reward** (`family_goal_reward`) | *(empty)* | up to 200 chars | Description of the reward earned when the goal is met |

### Negative Balance (v4.4.0)

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Allow negative balance** (`allow_negative_balance`) | `false` (off) | on / off | When on, point removals (penalties, manual deductions) may take a child below zero. When off, balances are floored at 0. See [Points Economy](Points-Economy.md). |

### Reminder Escalation (v4.4.0)

How long after a [mandatory chore](Mandatory-Chores.md) is missed before reminders escalate. Set via the websocket command `taskmate/notifications/set_escalation`. See [Reminder Escalation](Reminder-Escalation.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Child reminder escalation** (`mandatory_escalation_reminder_minutes`) | `30` | 1–1440 | Minutes after a miss before the child reminder escalates |
| **Parent alert escalation** (`mandatory_escalation_parent_minutes`) | `120` | 1–1440 | Minutes after a miss before the parent alert escalates |

### Calendar Subscription (v4.4.0)

| Setting | Default | Description |
|---------|---------|-------------|
| **ICS feed token** (`ics_token`) | *(auto-generated)* | Secret token in the iCal subscription URL. Generated on first use of the calendar feed; rotate it (via `taskmate/calendar/regenerate_ics_token`) to invalidate existing subscriptions. See [Calendar](Calendar.md). |

### Per-Child Quiet Hours (v4.4.0)

Set per child (in the child editor), not globally. During a child's quiet-hours window, TaskMate suppresses notifications to that child. A start later than the end defines an overnight window. See [Quiet Hours](Quiet-Hours.md).

| Setting | Default | Format | Description |
|---------|---------|--------|-------------|
| **Quiet hours start** (`quiet_hours_start`) | *(empty)* | `HH:MM` | Start of the do-not-disturb window; empty = no quiet hours |
| **Quiet hours end** (`quiet_hours_end`) | *(empty)* | `HH:MM` | End of the do-not-disturb window |

### Vacation Mode (v4.0.0)

Define named **vacation periods** (`vacation_periods`) — each with `id`, `name`, `start`, and `end` (inclusive ISO dates). While today falls inside a vacation period, streaks are frozen (missed days don't break the streak) and the daily streak check is skipped. The overview sensor exposes `vacation_active`, `vacation_name`, `vacation_end`, and the full `vacation_periods` list. See [Vacation Mode](Vacation-Mode.md).

---

### Chore Roulette (v5.0.0)

Off by default. Also needs `show_roulette: true` on the child card — it is doubly opt-in, so an existing dashboard never sprouts a new button. See [Chore Roulette](Chore-Roulette.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Roulette enabled** (`roulette_enabled`) | `false` (off) | on / off | Master toggle |
| **Roulette multiplier** (`roulette_multiplier`) | `2.0` | 1.0–5.0 | Points multiplier on the chore that comes up. Values below 1 are clamped to 1 — spinning should never punish the child. |
| **Daily spins** (`roulette_daily_spins`) | `1` | — | How many spins each child gets per day |

### Unlock Allowlist (v5.0.0)

The entities a [timed unlock reward](Timed-Unlock-Rewards.md) is permitted to turn on. An entry can be a full entity id (`switch.xbox`) or a bare domain (`switch`).

**An empty allowlist permits nothing.** This gates household devices, so the safe default when unconfigured is "no".

| Setting | Default | Description |
|---------|---------|-------------|
| **Unlock allowlist** (`unlock_allowlist`) | empty | Entity ids or domains a reward may unlock |

### Read Aloud (v5.0.0)

Wording comes from these parent-editable templates rather than TaskMate's translations — the frontend locales don't reach the backend, and a family may want phrasing that isn't one of the eight shipped languages. See [Read Aloud](Read-Aloud.md).

| Setting | Default | Placeholders |
|---------|---------|--------------|
| **Default media player** (`read_aloud_media_player`) | empty | — |
| **Default TTS entity** (`read_aloud_tts_entity`) | empty | — |
| `read_aloud_template` | `{name}, you have {count} things left: {chores}.` | `{name}` `{count}` `{chores}` |
| `read_aloud_one_template` | `{name}, you have one thing left: {chores}.` | same |
| `read_aloud_done_template` | `{name}, you're all done. Nice one!` | same |
| `read_aloud_joiner` | `and` | joins the last two chores |

A template with a bad placeholder logs a warning and falls back to the built-in wording rather than silencing the feature.

### Parent Approval Routing (v5.0.0)

Who gets buzzed when an approval is waiting. See [Multi-Parent Approval Routing](Multi-Parent-Approval-Routing.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Parent routing** (`parent_routing`) | `all` | `all` / `home` / `round_robin` | `all` notifies every enabled parent; `home` only those whose presence entity says they're here; `round_robin` one parent per notification, rotating. Every fallback errs towards over-notifying. |

### Streak Freezes (v6.0.0)

In **Settings → History & streaks**. A token saves a child's streak on one missed day. See [Streak Freezes](Streak-Freezes.md).

> **On by default.** Upgraded installs start using streak freezes straight away. To keep streaks working exactly as before, set **Max streak freezes** to `0`.

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Streak freezes (most a child can hold)** (`streak_freeze_max`) | `2` | 0–10 | The most tokens a child can hold. `0` turns streak freezes off |
| **Earn a streak freeze every** (`streak_freeze_earn_every`) | `7` | 0–365 | Consecutive streak days per free token. `0` = never earned automatically (offer a **Streak freeze** reward instead, or grant tokens with [`adjust_streak_freezes`](Services.md#taskmateadjust_streak_freezes-v600)) |

### Birthday Mode (v6.0.0)

In **Settings → History & streaks**. Each child's birthday itself is set under **Children → Edit** (see [Per-child settings](#per-child-settings-v600) below). See [Birthday Mode](Birthday-Mode.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Birthday points multiplier** (`birthday_points_multiplier`) | `2.0` | 1.0–5.0 | Chore points on a child's birthday, on top of the weekend bonus. `1.0` = no birthday bonus |
| **Birthday day off** (`birthday_chores_off`) | `off` | on / off | Hide non-mandatory chores on a child's birthday. The day never breaks their streak and never uses up a streak freeze |

### Quality Ratings (v6.0.0)

Rate each chore approval 1–3 stars and scale the points to match. An approval without a rating pays 100%. See [Quality Ratings](Quality-Ratings.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Quality ratings** (`quality_rating_enabled`) | `off` | on / off | Show the star picker on the approvals card, the panel approval queue and the phone approval notification |
| **★ multiplier** (`quality_rating_multiplier_1`) | `0.75` | 0.0–5.0 | Points multiplier for a one-star rating |
| **★★ multiplier** (`quality_rating_multiplier_2`) | `1.0` | 0.0–5.0 | Points multiplier for a two-star rating |
| **★★★ multiplier** (`quality_rating_multiplier_3`) | `1.25` | 0.0–5.0 | Points multiplier for a three-star rating |

### Child Undo Window (v6.0.0)

In **Settings → Parents**. See [Child Undo Window](Child-Undo-Window.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Child undo window (seconds)** (`chore_undo_seconds`) | `0` (off) | 0–3600 | Lets a child take back their own chore: a submission waiting for approval until a parent reviews it, and an automatically approved chore for this many seconds after they tapped it. Once a parent has reviewed a chore, only a parent can undo it |

### Recaps (v6.0.0)

In **Settings → Recaps**. Off until a frequency is ticked. See [Recaps](Recaps.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Family default** (`recap_frequencies`) | none (off) | any mix of `weekly`, `monthly`, `every_3_months`, `every_6_months`, `every_9_months`, `yearly` | The recaps every child on *Family default* gets. None ticked turns recaps off. Every 9 months runs in blocks counted from 1 January 2026 |
| **Per child** (`recap_child_frequencies`) | *Family default* | same list, per child | Override the family default for one child, e.g. weekly for a younger child and yearly for a teenager |
| **Notify when ready → Child's device** (`recap_notify_children`) | `on` | on / off | Send the child a **Recap ready** notification |
| **Notify when ready → Parents** (`recap_notify_parents`) | `on` | on / off | Send parents one grouped message |
| **Send at** (`recap_send_time`) | `08:00` | `HH:MM` | Recaps are built at midnight; the notification waits until this time |
| **Keep recaps for** (`recap_retention`) | `forever` | `1y` / `2y` / `forever` | Older recaps are deleted automatically |
| **Compare with previous period** (`recap_compare`) | `on` | on / off | Adds the "compared with last time" slide |

Nothing is sent while the **Recap ready** notification type is switched off on the Notifications tab. It is switched on for you the first time you turn recaps on.

### Surprise Inspections (v6.0.0)

In **Settings → Surprise inspections**. See [Surprise Inspections](Surprise-Inspections.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Inspections** (`inspections_enabled`) | `on` | on / off | Shows a 🔍 button on chores approved in the last 24 hours, in Today and Activity. Nothing happens until you press it |
| **Bonus for a pass** (`inspection_bonus`) | `10` | 0–10000 | Default bonus; can be changed for each inspection |
| **Time to check** (`inspection_window`) | `2h` | `1h` / `2h` / `4h` / `bed` | How long you have to pass or fail it. Unchecked inspections close with no bonus |
| **Bedtime** (`inspection_bedtime`) | `20:00` | `HH:MM` | Used by "Until bedtime". Less than 30 minutes before it, the window is an hour |
| **If it fails** (`inspection_fail_mode`) | `note` | `note` / `redo` / `ask` | Just note it, send the chore back to redo, or ask each time. No points are taken either way |
| **Tell the child when it starts** (`inspection_tell_child`) | `on` | on / off | Shows "Inspection coming" on their card. Turn off for secret checks |
| **Random daily pick** (`inspection_pick_enabled`) | `off` | on / off | TaskMate picks one approved chore for you to inspect; it shows up in **Needs you** |
| **Pick time** (`inspection_pick_time`) | `17:00` | `HH:MM` | When the daily pick is rolled |
| **Pick chance** (`inspection_pick_chance`) | `30` | 0–100 | Percent chance of a pick each day |
| **Pick children** (`inspection_pick_children`) | all | child IDs | Only these children's chores can be picked. None ticked means every child. Never the same child two days running |

### Presence-Aware Reminders (v6.0.0)

On the **Notifications** tab, under the **Arrived home** type. Each child's presence entity is set under **Children → Edit**. See [Presence-Aware Reminders](Presence-Aware-Reminders.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Only after being away for** (`presence_arrival_min_away`) | `30` | 0–1440 minutes | The "You're home" message is only sent if the child was away at least this long |

### Auto-Approve (v7.0.0)

In **Settings → Parents (no admin rights)**, below the child undo window. See [Auto-Approve](Auto-Approve.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Auto-approve after (hours)** (`auto_approve_hours`) | `0` (off) | 0–168 | A chore still waiting for approval this many hours after the child finished it approves itself, at the points the child was promised, exactly as if a parent had tapped Approve. Open-ended chores and bounties always wait for you. Checked once a minute |

### Personal Weekly Goals (v7.0.0)

In **Settings → Personal weekly goals**. See [Weekly Goals](Weekly-Goals.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Let children set a weekly goal** (`weekly_goal_enabled`) | `off` | on / off | Shows the goal on the child card, where each child picks their own points target for the week |
| **Bonus for reaching it** (`weekly_goal_bonus`) | `10` | 0–100000 | Paid once a week, the first time the child's points earned since Monday reach their goal. `0` = no bonus |

### Virtual Pets (v7.0.0)

In **Settings → Virtual pets**. Growth is counted from the day the pet is adopted. See [Virtual Pets](Virtual-Pets.md).

| Setting | Default | Range | Description |
|---------|---------|-------|-------------|
| **Turn on virtual pets** (`pets_enabled`) | `off` | on / off | Master toggle. Children adopt a pet on the Pet card |
| **Growth per chore** (`pet_xp_per_chore`) | `10` | 0–1000 | Growth added by every finished chore |
| **Chore points count too** (`pet_points_count`) | `on` | on / off | Each point earned adds 1 growth, so bigger jobs grow the pet faster. Spending points never shrinks it |
| **Hatches (baby)** (`pet_stage_baby`) | `30` | 1–1000000 | Growth needed to hatch |
| **Little** (`pet_stage_kid`) | `200` | 1–1000000 | Growth needed for the next stage |
| **Big** (`pet_stage_teen`) | `600` | 1–1000000 | Growth needed for the next stage |
| **Fully grown** (`pet_stage_grown`) | `1500` | 1–1000000 | Growth needed to be fully grown. The four stage numbers must go up in order |
| **Its home grows** (`pet_home_enabled`) | `on` | on / off | After fully grown, a new item for the pet's home every so often, up to 10 |
| **New home item every** (`pet_home_every`) | `300` | 1–1000000 | Growth between home items |
| **Turns legendary** (`pet_legendary_enabled`) | `on` | on / off | A gold, sparkling look after fully grown |
| **Legendary at** (`pet_legendary_at`) | `3000` | 1–1000000 | Total growth for legendary. Must be above **Fully grown** |
| **Lays an egg** (`pet_eggs_enabled`) | `on` | on / off | The child hatches the egg into a new pet; the old one joins the pet family |
| **Egg at** (`pet_egg_at`) | `3000` | 1–1000000 | Used when legendary is off; otherwise the egg comes with legendary |
| **Largest pet family** (`pet_family_max`) | `6` | 2–12 | Pets per child, counting the current one. No more eggs once it's full |
| **Pet levels** (`pet_levels_enabled`) | `off` | on / off | A level badge that keeps going up after fully grown |
| **New level every** (`pet_level_every`) | `300` | 1–1000000 | Growth between pet levels |

A pet never loses a stage, home item, level or egg it has reached: raising a number, undoing a chore or turning an option off only changes what happens next. **Reset numbers to defaults** puts every number back.

### Per-child settings (v6.0.0)

Set under **Children → Edit** for each child, not globally.

| Setting | Format | Description |
|---------|--------|-------------|
| **Birthday** (`birthday`) | `YYYY-MM-DD`, or `MM-DD` to leave the age off | Turns on [Birthday Mode](Birthday-Mode.md) for that day. 29 February is celebrated on 28 February in other years |
| **Age group** (`age_group`) | `3_5` / `6_8` / `9_12` / `13_plus` | Used by the [Setup Wizard](Setup-Wizard.md) to suggest chores when no birthday is given |
| **Presence (for reminders)** (`presence_entity`) | a `person.*` or `device_tracker.*` entity | While it isn't `home`, this child's reminders are held back. An `unavailable` tracker counts as home. See [Presence-Aware Reminders](Presence-Aware-Reminders.md) |
| **Colour** (`color`) | `#rrggbb`, or *Automatic* | (v7.0.0) Marks this child's avatar and name in the admin panel. *Automatic* picks one from the child's place in the list |
| **Kiosk PIN** | 4 digits | Asked for on a shared [kiosk](Kiosk-Mode.md) tablet. Stored hashed, so it can't be read back; leave blank to keep the current PIN |

### Setup Wizard (v6.0.0)

**Settings → Run setup wizard** opens the [Setup Wizard](Setup-Wizard.md) again at any time (it is also in the command search, **Ctrl K**). It only ever adds children, chores, rewards and dashboards; it never deletes anything.

### Ready-Made Dashboards (v6.3.0)

**Settings → Ready-made dashboards** creates a Kids, Parents or Wall tablet dashboard filled in with your children (also in the command search, **Ctrl K**). An existing dashboard is never overwritten. See [Ready-Made Dashboards](Ready-Made-Dashboards.md).

## Where Settings Apply

- **Currency name and icon** — shown on all cards, sensors, and notifications
- **Weekend multiplier** — applied automatically when `approve_chore` runs on a Saturday or Sunday
- **Streak settings** — checked at midnight (00:00:05) daily; milestones checked on each chore approval
- **Perfect week** — checked Monday at midnight for the previous Mon–Sun period
- **Notification service** — fires on every pending chore approval and pending reward claim
- **Calendar projection** — recalculated at midnight and whenever a chore is created or edited
- **History pruning** — runs daily at 00:01
- **Time-of-day boundaries / periods** — affect calendar event windows and the time-category each chore falls into
- **Difficulty multipliers** — applied to base points at chore approval
- **Surprise bonus** — rolled per child daily at 16:00 when enabled
- **Points decay / savings interest** — applied on the configured period boundary (Monday for weekly, the 1st for monthly)
- **Spending cap** — checked when a reward claim is approved
- **Celebrations** — notifications fire on level-ups, milestones, perfect weeks, and quest/challenge completions
- **Vacation mode** — checked at midnight during the daily streak check
- **Default card design** — the style applied to every card left on *Use global default*
- **Allowance** — applied when a payout is recorded; converts points to cash at the fixed rate
- **Family goal** — checked after point changes; fires when combined points reach the target
- **Allow negative balance** — applied at every point removal
- **Reminder escalation** — timed off each mandatory miss
- **Quiet hours** — checked per child before each notification is delivered
- **Calendar subscription token** — used to authenticate the iCal feed URL
- **Streak freezes** — earned as the streak grows; spent in the midnight streak check on a missed day
- **Birthday mode** — applied on the child's birthday, from midnight
- **Quality ratings** — applied when a rated chore is approved
- **Child undo window** — checked when a child taps a done chore to undo it
- **Recaps** — built just after midnight at the end of each period; announced at the send time
- **Surprise inspections** — the random pick rolls daily at the pick time; a parent reminder goes out 30 minutes before an undecided inspection closes
- **Presence** — checked before each reminder, and when the child's tracker changes to `home`
- **Auto-approve** — checked once a minute against every chore waiting for approval
- **Weekly goals** — checked once a minute; the bonus is paid at most once per child per week (weeks start Monday)
- **Virtual pets** — growth is worked out from the child's chores and points since adoption; new stages are announced within a minute

---

## Related

- [Bonus Points](Bonus-Points.md) — detailed explanation of weekend multiplier, streaks, and perfect week
- [Difficulty Tiers](Difficulty-Tiers.md) — difficulty multipliers
- [Points Economy](Points-Economy.md) — surprise bonus, points decay, savings interest, and the spending cap
- [Levels and XP](Levels-and-XP.md) — the XP-per-level setting
- [Celebrations](Celebrations.md) — celebration notification tiers
- [Vacation Mode](Vacation-Mode.md) — vacation periods and streak freezing
- [Card Design Styles](Card-Design-Styles.md) — the global **Default card design** selector and per-card overrides
- [Allowance](Allowance.md) — converting points into a real-money allowance
- [Family Goals](Family-Goals.md) — the shared co-op goal
- [Reminder Escalation](Reminder-Escalation.md) — mandatory-miss reminder escalation timings
- [Quiet Hours](Quiet-Hours.md) — per-child do-not-disturb windows
- [Configuration Entities](Configuration-Entities.md) — settings surfaced as HA number/select entities
- [Weekly Digest](Weekly-Digest.md) — the Sunday parent summary
- [Notifications](Notifications.md) — notification setup and examples
- [Calendar](Calendar.md) — per-child calendar entities and publishing details
- [Chore Roulette](Chore-Roulette.md) — the roulette multiplier and daily spins
- [Timed Unlock Rewards](Timed-Unlock-Rewards.md) — the unlock allowlist
- [Read Aloud](Read-Aloud.md) — the spoken-summary templates
- [Multi-Parent Approval Routing](Multi-Parent-Approval-Routing.md) — the `parent_routing` setting
- [Streak Freezes](Streak-Freezes.md), [Birthday Mode](Birthday-Mode.md), [Quality Ratings](Quality-Ratings.md), [Child Undo Window](Child-Undo-Window.md), [Recaps](Recaps.md), [Surprise Inspections](Surprise-Inspections.md), [Presence-Aware Reminders](Presence-Aware-Reminders.md), [Kiosk Mode](Kiosk-Mode.md), [Setup Wizard](Setup-Wizard.md) — v6.0.0 settings
- [Auto-Approve](Auto-Approve.md), [Weekly Goals](Weekly-Goals.md), [Virtual Pets](Virtual-Pets.md) — v7.0.0 settings
- [Getting Started](Getting-Started.md) — initial currency setup
