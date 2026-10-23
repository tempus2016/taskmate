# Sensor Attributes

TaskMate exposes one primary overview sensor and a set of per-child sensors. Automations, templates, and custom cards can read from these.

![TaskMate entity attributes in Developer Tools → States](images/dev-tools-states.png)

## `sensor.taskmate_overview`

**State**: number of children.

This is the main sensor. Its `extra_state_attributes` contain everything most cards and automations need.

### Top-level attributes

| Attribute | Type | Description |
| --- | --- | --- |
| `total_children` | int | Number of children |
| `total_chores` | int | Number of defined chores |
| `total_rewards` | int | Number of defined rewards |
| `total_points_available` | int | Sum of all children's points |
| `total_chores_completed` | int | Lifetime chore completions |
| `total_completions_all_time` | int | Lifetime chore completion records |
| `total_pending_completions` | int | Chore completions awaiting approval |
| `today_day_of_week` | string | Lowercase day name, e.g. `"friday"` |
| `points_name` | string | Customisable points currency name |
| `points_icon` | string | MDI icon string |
| `card_design` | string | (v4.1.0) Global default [card design style](Card-Design-Styles.md) — `classic` / `playroom` / `console` / `cleanpro` / `accessible` (default `classic`); cards apply it when they have no per-card override |
| `children` | list | Per-child objects (see below) |
| `chores` | list | Per-chore objects |
| `rewards` | list | Per-reward objects (see below) |
| `todays_completions` | list | Chore completions logged today |
| `pending_reward_claims` | list | Reward claims awaiting approval |
| `pool_allocations` | list | (v3.0+) Raw `PoolAllocation` records |
| `time_boundaries` | dict | Legacy fixed time-window map (`morning_start`/`morning_end`/…) in `HH:MM` |
| `time_periods` | list | (v4.0+) Custom time-of-day periods — each `id`, `label`, `start`, `end`, `icon`. See [Settings](Settings.md#custom-time-of-day-periods-v400) |
| `vacation_active` / `vacation_name` / `vacation_end` | bool / string | (v4.0+) Active [vacation period](Vacation-Mode.md) state |
| `vacation_periods` | list | (v4.0+) All configured vacation periods (`id`, `name`, `start`, `end`) |
| `family_goal` | object | (v4.4.0) Shared co-op [family goal](Family-Goals.md) state (`enabled`, `name`, `target`, `progress`, `reward`, `achieved`) |
| `season_month` | string | (v4.4.0) Current leaderboard season month, `YYYY-MM`. See [Leaderboard Seasons](Leaderboard-Seasons.md) |
| `season_champions` | list | (v4.4.0) Past monthly leaderboard champions (newest first, up to 12) |
| `companion_entities` | dict | (v6.1.0) Where each companion sensor really lives: role (`chores`, `rewards`, `activity`, `bounties`, `auctions`, `chore_board`, …) → entity ID. Cards use it to find sensors that Home Assistant created with an area prefix or that you renamed. Not recorded in history |
| `badge_entities` | dict | (v6.1.0) Child ID → that child's badges sensor entity ID. Not recorded in history |
| Settings mirrors | various | `streak_reset_mode`, `weekend_multiplier`, `streak_milestones_enabled`, `streak_milestones`, `perfect_week_enabled`, `perfect_week_bonus`, and (v6.0.0) `streak_freeze_max`, `streak_freeze_earn_every` |

> **Note:** Heavy lists (`chores`, `rewards`, `todays_completions`, `recent_completions`, `recent_transactions`, `pending_reward_claims`, `pool_allocations`) have been moved to companion sensors (`sensor.taskmate_chores`, `sensor.taskmate_rewards`, `sensor.taskmate_activity`). Cards merge them transparently via the `__taskmate_attrs` helper. See [Sensor Reference](Sensor-Reference.md) for full details.

### `children[]` entries

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Stable child ID |
| `name` | string | Display name |
| `avatar` | string | MDI icon (currently selected avatar) |
| `avatar_image` | string | (v6.4.0) The child's [photo](Children.md#child-photos), from their **Photo from** entity. Empty when there is none; cards then show `avatar` |
| `is_adult` | bool | (v6.4.0) `true` for an [adult profile](Adult-Profiles.md). Present only for adults |
| `level` | int | (v4.0+) XP level derived from `total_points_earned`. See [Levels and XP](Levels-and-XP.md) |
| `level_progress` | int | (v4.0+) XP into the current level band |
| `level_target` | int | (v4.0+) XP per level (`level_xp_step`, default 100) |
| `points` | int | Gross balance (after pool deposits have been subtracted) |
| `pending_points` | int | Points earned from approved chores not yet applied |
| `committed_points` | int | Points tied up in pending reward claims |
| `spendable_balance` | int | (v3.0+) `points − committed_points` — what the child can spend or deposit now |
| `allocated_points` | int | (v3.0+) Total points the child has deposited across all pools |
| `total_points_earned` | int | Lifetime points earned |
| `total_chores_completed` | int | Lifetime chores completed |
| `current_streak` | int | Current consecutive-day streak |
| `best_streak` | int | Highest streak achieved |
| `season_points` | int | (v4.4.0) Points earned this leaderboard season (current month). See [Leaderboard Seasons](Leaderboard-Seasons.md) |
| `week_points_earned` | int | (v6.4.0) Approved chore points since Monday (bonus sub-tasks excluded). Used by the [Sticker Chart](Sticker-Chart-Card.md)'s week goal |
| `week_points_available` | int | (v6.4.0) The most this week's scheduled chores could pay, with the weekend multiplier and without vacation days. Rotation chores aren't counted, so `week_points_earned` can run past it |
| `last_completion_date` | string \| null | ISO date of last completion |
| `streak_paused` | bool | `true` if streak is currently paused |
| `streak_milestones_achieved` | list[int] | Streak milestones unlocked |
| `awarded_perfect_weeks` | list[string] | ISO Monday dates of perfect weeks |
| `chore_order` | list[string] | Custom ordering of chore IDs |
| `career_score` | int | Long-term performance metric (`total_points_earned − total_penalties_received`) |
| `total_penalties_received` | int | Lifetime count of penalties applied |
| `quests` | list | (v4.0+) Per-child [quest](Quests.md) progress (`quest_id`, `name`, `icon`, `total_steps`, `step`, `done`, `times_completed`, `bonus_points`, `next_chore_id`) |
| `challenges` | list | (v4.0+) Per-child [challenge](Challenges.md) progress (`challenge_id`, `name`, `icon`, `scope`, `metric`, `target`, `progress`, `value`, `bonus_points`, `complete`, `awarded`) |
| `avatar_options` | list | (v4.0+) [Avatar](Avatars.md) catalogue for this child (`id`, `label`, `icon`, `unlocked`, `requirement`) |
| `birthday` | object | (v6.0.0) Only on the child's [birthday](Birthday-Mode.md): `multiplier`, `age` (when the year is known), `chores_off` |
| `streak_freezes` | int | (v6.0.0) [Streak freeze](Streak-Freezes.md) tokens held. Only present while streak freezes are on |
| `rejections` | list | (v6.0.0) Items sent back with a [reason](Reject-Reasons.md) in the last 24 hours (`kind`, `id`, `reason`, `at`). Only present when there is one |
| `inspections` | list | (v6.0.0) Today's [inspection](Surprise-Inspections.md) banners (`id`, `chore_id`, `name`, `status`, plus `bonus` / `until` / `points` / `note` where relevant). Only present when there is one |
| `help` | list | (v7.0.0) Chore IDs with an open [help request](Help-Requests.md). Present only when there is one |
| `mood_today` | string | (v7.0.0) Today's [mood](Mood-Check-In.md) (`great` / `good` / `ok` / `sad` / `upset`), once the child has said |
| `sick_today` | bool | (v7.0.0) `true` on a [sick day](Sick-Days.md). Present only then |
| `pet` | object | (v7.0.0) The child's [virtual pet](Virtual-Pets.md) (`adopted`, `name`, `species`, `stage`, `mood`, `xp`, `accessories`, …). Present only while pets are on |
| `weekly_goal` | object | (v7.0.0) The child's [weekly goal](Weekly-Goals.md) (`target`, `bonus`, `earned`, `reached`). Present only while weekly goals are on |
| `redemptions` | list | (v7.0.0) Open [make-it-right](Make-It-Right-Penalties.md) offers (`id`, `chore_id`, `chore_name`, `penalty_name`, `points`, `expires`). Present only when there is one |
| `owed_rewards` | list | (v7.1.0) Redeemed rewards still to hand over (`claim_id`, `reward_name`, `reward_icon`, `days_owed`). Present only while [reward fulfilment](Reward-Fulfilment.md) is on and something is owed |
| `chore_streaks` | dict | `{chore_id: days}` — [per-chore streaks](Per-Chore-Streaks.md) of two days or more. Present only when there is one |
| `tomorrow` | list | Chore ids due tomorrow, for the [tomorrow preview](Tomorrow-Preview.md). Present only when something is due |
| `reminders` | dict | `{chore_id: "HH:MM"}` — the child's own [reminder times](Child-Chosen-Reminders.md), while the feature is on |
| `praise` | list | Today's [praise notes](Praise-Notes.md), newest first, up to 3 (`chore_name`, `note`, `by`) |
| `penalty_warnings` | list | [Penalty warnings](Penalty-Warnings.md) given this period and not yet spent (`penalty_id`, `name`, `points`) |
| `sibling_checks` | list | Siblings' chores this child may [check](Sibling-Checks.md), up to 5 (`completion_id`, `child_id`, `child_name`, `chore_name`, `completed_at`, `photo`) |
| `personal_bests` | object | (v7.1.0) The child's [records](Personal-Bests.md): one object per record key (`value`, `date`, plus `previous` on a record beaten today) and `new_today`, the keys beaten today. Present once there is a record |

> Full field-by-field tables for `quests`, `challenges`, and `avatar_options` are in the [Sensor Reference](Sensor-Reference.md#children-array).

### `rewards[]` entries

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Stable reward ID |
| `name` | string | Display name |
| `description` | string | Optional description |
| `icon` | string | MDI icon |
| `cost` | int | Points cost |
| `assigned_to` | list[string] | Child IDs the reward applies to (empty = all) |
| `is_jackpot` | bool | Community goal — pools across all assigned children |
| `pool_enabled` | bool | (v3.0+) When `true`, this reward uses savings-jar semantics |
| `calculated_costs` | `{child_id: int}` | Per-child cost (currently static; all equal `cost`) |
| `pool_allocations` | `{child_id: int}` | (v3.0+) Points each assigned child has deposited |
| `jackpot_pool_total` | int \| null | (v3.0+) Combined pool for jackpot rewards; `null` otherwise |
| `quantity` | int \| null | Remaining stock (`null` = unlimited) |
| `expires_at` | string \| null | ISO date expiry deadline (`null` = never) |
| `is_sold_out` | bool | `true` when quantity has reached 0 |
| `is_expired` | bool | `true` when past the expiry date |
| `is_available` | bool | `true` when not sold out and not expired |
| `days_until_expiry` | int \| null | Days remaining until expiry (`null` if no expiry set) |
| `streak_freeze` | bool | (v6.0.0) `true` on a **Streak freeze** reward. Only present when set |

### `chores[]` entries

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Stable chore ID |
| `name`, `description` | string | Display |
| `points` | int | Base points awarded on approval |
| `difficulty` | string | (v4.0+) `easy`/`medium`/`hard` — only present when not `medium`. See [Difficulty Tiers](Difficulty-Tiers.md) |
| `effective_points` | int | (v4.0+) Points after the difficulty multiplier — present only when it differs from `points` |
| `mandatory` | bool | (v4.2.0) `true` for a [mandatory chore](Mandatory-Chores.md) — only present when set |
| `mandatory_penalty_points` | int | (v4.2.0) Penalty deducted if missed — only present when `mandatory` is set and the penalty is non-zero. See [Mandatory Chores](Mandatory-Chores.md) |
| `assigned_to` | list[string] | Child IDs (empty = all) |
| `time_category` | string | `morning` / `afternoon` / `evening` / `night` / `anytime` |
| `daily_limit` | int | Max completions per child per day |
| `completion_sound` | string | Sound identifier |
| `schedule_mode` | string | `specific_days`, `recurring`, or `one_shot` |
| `assignment_mode` | string | `everyone` / `alternating` / `random` / `balanced` / `first_come` / `unassigned` |
| `due_days` | list[string] | Used in `specific_days` mode |
| `recurrence` / `recurrence_day` / `recurrence_start` | — | Used in `recurring` mode |
| `first_occurrence_mode` | string | `available_immediately` / `wait_for_first_occurrence` |
| `visibility_entity` / `visibility_state` / `visibility_operator` | — | Optional dynamic visibility guard |
| `enabled` | bool | False = soft-disabled (one-shot completed or expired) |
| `disabled_for` | list[string] | Child IDs this chore is disabled for |
| `created_date` | string | ISO date for one-shot chore expiry |
| `last_completed_at` | `{child_id: iso}` | Most recent completion per child |
| `is_available` | `{child_id: bool}` | Whether chore shows for each child today |
| `task_type` | string | `standard` or `timed` |
| `timed_rate_points` | int | Points per rate window (timed chores) |
| `timed_rate_minutes` | int | Rate window in minutes (timed chores) |
| `timed_max_daily_minutes` | int | Daily cap in minutes; 0 = unlimited (timed chores) |
| `bonus_subtasks` | list[dict] | Embedded subtasks — each has `id`, `name`, `points`, `description` |
| `require_availability` | bool | Skip unavailable children in rotation |
| `manual_start_child_id` | string | Forced rotation start child ID (if set) |
| `publish_calendar_entities` | list[string] | HA calendar entity IDs for publishing |
| `team` | object | (v6.0.0) [Teamwork chores](Teamwork-Chores.md) only: `size`, `joined` (child IDs), `split` |
| `occ_today` | bool | (v6.0.0) Overrides whether the chore is due today — after a [calendar](Two-Way-Calendar.md) move or skip, or for a one-off dated another day |
| `moved_occurrences` | `{iso: iso}` | (v6.0.0) Calendar moves, original date → new date (empty = skipped) |
| `auction_wins` / `auction_prices` / `auction` | dict / dict / object | (v6.0.0) [Auction](Chore-Auctions.md) results this week: winner and price per day, and today's `{child_id, points}` |
| `estimated_minutes` | int | (v7.0.0) [Estimated minutes](Estimated-Minutes.md). Only present when set |
| `quantity_unit` / `quantity_max` / `unit_points` | string / int / float | (v7.0.0) [Quantity chores](Quantity-Chores.md): the unit, the per-completion cap (when set) and the unrounded per-unit worth (when it differs from `effective_points`) |

### `pending_reward_claims[]` entries

| Field | Type | Description |
| --- | --- | --- |
| `claim_id` | string | Claim ID |
| `reward_id` | string | Reward ID |
| `child_id` | string | Child ID |
| `child_name` | string | Display name |
| `child_avatar` | string | MDI icon |
| `reward_name` | string | Display name |
| `reward_icon` | string | MDI icon |
| `cost` | int | Points cost |
| `claimed_at` | string | ISO datetime |

## `sensor.taskmate_pending_approvals`

**State**: total pending (chores + claims).

Attributes include `pending_chore_completions`, `pending_reward_claims`, `pending_mandatory_misses` (count), `chore_completions` (enriched list; a finished [bounty](Bounty-Board.md) carries `bounty_id`), `reward_claims` (enriched list; a [wish](Wishlist.md) being redeemed appears here like a reward), `quality_rating` (v6.0.0, present only while [quality ratings](Quality-Ratings.md) are on — `multipliers` for ★, ★★, ★★★), (v7.0.0) `quantity` / `quantity_unit` and a signed `reference_image_url` on chore completions where the chore has them ([Quantity Chores](Quantity-Chores.md), [Reference Photos](Reference-Photos.md)), and `mandatory_misses` (enriched list of [mandatory-miss](Mandatory-Chores.md) review items — each has `id`, `chore_id`, `child_id`, `chore_name`, `child_name`, `due_date`, `period_id`, `penalty_points`, `postpone_count`, `created_at`). See [Sensor Reference](Sensor-Reference.md#sensortaskmate_pending_approvals) and [Mandatory Chores](Mandatory-Chores.md).

## Per-child sensors

Each child gets two sensors created at onboarding:

- **`sensor.taskmate_<child_name>_points`** — state is current gross balance; attributes include `child_id`, `child_name`, `avatar`, `avatar_image` (v6.4.0), `total_points_earned`, `total_chores_completed`, `current_streak`, `best_streak`
- **`sensor.taskmate_<child_name>_stats`** — state is total chores completed; attributes include `child_id`, `child_name`, `avatar`, `avatar_image` (v6.4.0), `points`, `total_points_earned`, `total_chores_completed`, `current_streak`, `best_streak`, `assigned_chores` (list of today's assigned chores), `chore_order`. From v6.4.0 the stats sensor's entity picture is the child's [photo](Children.md#child-photos) when they have one

(v6.0.0) Two more per child:

- **`sensor.taskmate_<child_name>_wishlist`** — state is the number of wishes on the go; attributes `wishlist_child_id`, `wish_max_open` and `wishes` (each `id`, `name`, `target`, `status`, and when set `saved`, `pledged`, `pledges`, `link`, `image_url`, `decline_reason`). See [Wishlist](Wishlist.md)
- **`sensor.taskmate_<child_name>_watch`** — state is a short phrase such as `3 left`, `All done` or `No chores`, in Home Assistant's language; attributes `child_id`, `status` (`to_do` / `all_done` / `no_chores`), `left`, `done`, `total`, `progress` (0–1), `points`, `streak`, `next_chore`. See [Watch Complications](Watch-Complications.md)

## Companion sensors

The overview sensor's heavy data has been split across companion sensors to stay under the 16KB recorder limit:

| Sensor | State | Key attributes |
|--------|-------|----------------|
| `sensor.taskmate_chores` | Chore count | `chores`, `todays_completions` |
| `sensor.taskmate_chore_availability` | Available chore/child pairs | `chore_availability` (matrix `{chore_id: {child_id: bool}}`) |
| `sensor.taskmate_rewards` | Reward count | `rewards`, `pending_reward_claims`, `pool_allocations`, (v7.0.0) `raffles` — open [raffles](Raffles.md) and those finished in the last day. Not recorded in history |
| `sensor.taskmate_activity` | All-time completion count | `recent_completions` (max 35), `recent_transactions` (max 20), `career_score_history`, `photo_gallery` (v4.4.0, max 40) |
| `sensor.taskmate_incentives` | Penalty + bonus count | `penalties`, `bonuses`, `task_groups` |
| `sensor.taskmate_bounties` | Open bounty count | (v6.0.0) `bounties` — the [bounty board](Bounty-Board.md): live bounties plus the last 24 hours' completed ones |
| `sensor.taskmate_auctions` | Open auction count | (v6.0.0) `auctions` — open and recently closed [auctions](Chore-Auctions.md): bid counts and results only, never bid amounts |
| `sensor.taskmate_chore_board` | Chores still to do today | (v6.1.0) `chore_board` — today's board for every child, as shown on the panel's Today page and the [Chore Board card](Dashboard-Cards.md#chore-board-card). Not recorded in history |

See [Sensor Reference](Sensor-Reference.md) for full attribute details.

## Attributes and the recorder *(v5.3.0+)*

The large list attributes above — `chores`, `recent_completions`,
`mandatory_misses`, `children`, the badge `earned` / `available` lists and so
on — are declared **unrecorded**.

They are still published on the live state, so **cards, `state_attr()`,
templates and automation conditions read them exactly as before**. Only Home
Assistant's recorder skips them, which keeps the database small and prevents
this warning:

```
WARNING (Recorder) State attributes for sensor.taskmate_activity exceed
maximum size of 16384 bytes. This can cause database performance issues;
Attributes will not be stored
```

Scalar attributes (counts, totals, settings) stay recorded, so history and
statistics on them keep working. The practical difference is that you cannot
look up a *past* value of one of the big lists in history — the current value is
always available on the state.

## Calendar entities

(v4.2.0) One calendar entity per child — **`calendar.taskmate_<child>`** (friendly name `TaskMate <child>`). It projects the child's upcoming chore occurrences and shows [away periods](Vacation-Mode.md) as all-day "Away" events; the state is the next upcoming event. Since v6.0.0 parents and admins can add, move and skip chores in it — see [Two-Way Calendar](Two-Way-Calendar.md). See [Calendar](Calendar.md) and [Sensor Reference](Sensor-Reference.md#calendar-entities-v420).

## To-do and configuration entities

(v4.4.0) TaskMate also creates:

- **`todo.taskmate_<child>`** — one to-do list per child of the chores they still need to do today; checking an item off completes that chore.
- **`number.taskmate_weekend_multiplier`**, **`number.taskmate_perfect_week_bonus`**, **`select.taskmate_streak_reset_mode`**, **`select.taskmate_card_design`** — key settings surfaced as entities, in sync with the admin panel.

See [Sensor Reference](Sensor-Reference.md#configuration-entities-v440) and [Configuration Entities](Configuration-Entities.md).

## Event entities

(v7.0.0) One **`event.taskmate_<child>_activity`** entity per child, plus **`event.taskmate_family_activity`**. They re-publish TaskMate's bus events, with the event's data as attributes, so they can be picked in the UI automation editor. See [Event Entities](Event-Entities.md) and [Sensor Reference](Sensor-Reference.md#event-entities-v700).

## Related

- [Services](Services.md) — services that modify these attributes
- [Sensor Reference](Sensor-Reference.md) — full entity + attribute catalogue, including companion sensors and admin-panel-only data
- [Pool Mode (Savings Jars)](Pool-Mode-(Savings-Jars).md) — context for the v3.0 pool attributes
- [Levels and XP](Levels-and-XP.md), [Quests](Quests.md), [Challenges](Challenges.md), [Avatars](Avatars.md), [Vacation Mode](Vacation-Mode.md) — v4.0.0 features that surface in these attributes
- [Mandatory Chores](Mandatory-Chores.md), [Card Design Styles](Card-Design-Styles.md), [Calendar](Calendar.md) — v4.1.0–v4.2.0 features that surface in these attributes
- [Family Goals](Family-Goals.md), [Leaderboard Seasons](Leaderboard-Seasons.md), [Allowance](Allowance.md), [Photo Proof](Photo-Proof.md), [Configuration Entities](Configuration-Entities.md) — v4.4.0 features that surface in these attributes
- [Birthday Mode](Birthday-Mode.md), [Streak Freezes](Streak-Freezes.md), [Reject Reasons](Reject-Reasons.md), [Surprise Inspections](Surprise-Inspections.md), [Teamwork Chores](Teamwork-Chores.md), [Chore Auctions](Chore-Auctions.md), [Bounty Board](Bounty-Board.md), [Wishlist](Wishlist.md), [Watch Complications](Watch-Complications.md) — v6.0.0 features that surface in these attributes
- [Help Requests](Help-Requests.md), [Mood Check-In](Mood-Check-In.md), [Sick Days](Sick-Days.md), [Virtual Pets](Virtual-Pets.md), [Weekly Goals](Weekly-Goals.md), [Make-It-Right Penalties](Make-It-Right-Penalties.md), [Raffles](Raffles.md), [Estimated Minutes](Estimated-Minutes.md), [Quantity Chores](Quantity-Chores.md), [Reference Photos](Reference-Photos.md), [Event Entities](Event-Entities.md) — v7.0.0 features that surface in these attributes
