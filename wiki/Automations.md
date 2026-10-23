# Automations

Examples of useful automations using TaskMate sensors and services.

---

## Internal Scheduled Tasks

TaskMate runs several automatic tasks on a schedule. These are **not** HA automations — they run inside the integration.

### Midnight tasks (00:00:05)

| Task | Description |
|------|-------------|
| **Streak check** | Updates each child's streak. In `reset` mode: missed days reset the streak to 0. In `pause` mode: missed days freeze the streak until the next completion. |
| **One-shot chore expiry** | Disables any one-shot chores created on the previous day. |
| **Assignment rotation** | Recomputes `assignment_current_child_id` for chores using `alternating`, `random`, or `balanced` modes. Task group policies (sticky/spread) are applied after raw picks. |
| **Calendar publishing** | Publishes chore assignment events to configured HA calendar entities, projected ahead by the configured number of days. Uses configurable time-of-day boundaries (v3.6.0+). |
| **Perfect week check** | Runs on **Mondays only**. Awards the perfect week bonus to any child who completed at least one chore every day the previous week (Mon–Sun). |
| **Stale timed session cleanup** | Stops any timed task sessions left running from previous days. Creates completion records with elapsed time up to midnight. |
| **Career score snapshot** | Saves each child's career score for historical tracking. Prunes snapshots older than 90 days. |
| **Skip state reset** | Clears ephemeral skip data (`skip_date`, `skip_count`) from the previous day. |

### History pruning (00:01:00)

Trims old completion records to the configured **History Days** setting (default: 90 days, range: 30–365).

### Availability monitoring (real-time)

TaskMate listens for `state_changed` events on all entities configured as a child's **Availability Entity**. When a tracked entity changes state:

1. TaskMate re-evaluates which children are available
2. Chores with **Require Availability** enabled recompute their assignments
3. Unavailable children are skipped in `alternating`, `random`, and `balanced` rotation

**Recognised "available" states:** `on`, `home`, `available`, `present`, `true`. Any other state (including `unavailable`, `off`, `unknown`) is treated as unavailable.

### Assignment rotation algorithms

| Mode | Algorithm |
|------|-----------|
| `alternating` | Round-robin using `(today - anchor_date) mod pool_size` to pick the child index |
| `random` | Deterministic daily pick using `SHA256(chore_id + date)` — stable within a day, changes at midnight |
| `balanced` | Groups all balanced-mode chores sharing the same child pool, sorts by ID, and distributes evenly via round-robin so no child gets more than one extra chore |

### Task group assignment

After raw per-chore rotation picks are calculated:

1. **Sticky groups:** The first chore (leader) keeps its pick. All followers are forced onto the leader's child, provided that child is in their pool. If not, followers fall back to their own pick.
2. **Spread groups:** Each chore is assigned a different child. The algorithm walks forward from each chore's raw pick to find an unused child, wrapping if more chores than children.

### Calendar event format

When chores are published to a calendar, the events look like this:

- **Title:** `Wash Dishes — Tommy` (chore name + assigned child)
- **Time-based chores** create timed events matching the time category:

| Time category | Event window |
|---------------|-------------|
| `morning` | 06:00–12:00 |
| `afternoon` | 12:00–17:00 |
| `evening` | 17:00–21:00 |
| `night` | 21:00–23:59 |
| `anytime` | All-day event |

- **Description** contains an internal marker (`taskmate:chore:<id>`) used for cleanup — do not edit it manually
- Events are only published for dates not already in the calendar (idempotent)
- When a chore is deleted or edited, old calendar events are automatically cleaned up

### Automatic reward expiry & refunds

At midnight, rewards past their **expiration date** are marked expired. Pool allocations for expired rewards are **automatically refunded** to each child's spendable balance. The same refund logic runs when a reward's cost is reduced below a child's current allocation.

### Timed task auto-stop

Stale timed sessions (sessions from a previous day still in `running` or `paused` state) are automatically stopped at midnight. A completion record is created using the elapsed time accumulated up to that point. This prevents children from accidentally leaving timers running overnight.

---

## Bus Events Reference

TaskMate fires Home Assistant bus events for most state changes. Trigger your own automations off them with an `event` trigger. Every event carries a `timestamp` (ISO 8601) unless noted, and most carry `child_id` / `child_name`.

### Points, rewards & penalties

| Event | Data fields |
|-------|-------------|
| `taskmate_penalty_applied` | `child_id`, `child_name`, `penalty_id`, `penalty_name`, `points`, `timestamp` |
| `taskmate_bonus_applied` | `child_id`, `child_name`, `bonus_id`, `bonus_name`, `points`, `timestamp` |
| `taskmate_points_gifted` | `from_child_id`, `from_child_name`, `to_child_id`, `to_child_name`, `points`, `timestamp` |
| `taskmate_points_decay` | `child_id`, `child_name`, `points`, `timestamp` |
| `taskmate_interest_paid` | `child_id`, `child_name`, `points`, `timestamp` |
| `taskmate_surprise_bonus` | `child_id`, `child_name`, `points`, `timestamp` |
| `taskmate_perfect_week` | `child_id`, `week_key`, `bonus`, `timestamp` |

### Chores

| Event | Data fields |
|-------|-------------|
| `taskmate_chore_completed` | `child_id`, `child_name`, `chore_id`, `chore_name`, `points`, `difficulty`, `timestamp` |
| `taskmate_chore_approved` | `child_id`, `chore_id`, `completion_id`, `timestamp` |
| `taskmate_chore_rejected` | `child_id`, `child_name`, `chore_id`, `chore_name`, `completion_id`, `reason` (v6.0.0, empty when none was given), `timestamp` |
| `taskmate_swap_approved` | `chore_id`, `requester_id`, `from_child_id`, `timestamp` |
| `taskmate_weekly_target_reached` | `child_id`, `child_name`, `chore_id`, `chore_name`, `target`, `bonus`, `timestamp` — (v6.2.0) a child's approved completions reached a chore's [weekly target](Weekly-Targets.md#weekly-target-bonus) and the bonus was paid. Only fires on chores with a bonus set, once per child, chore and week |

### Rewards

| Event | Data fields |
|-------|-------------|
| `taskmate_reward_claimed` | `child_id`, `reward_id`, `claim_id`, `cost`, `recipient_id` (a gift only), `timestamp` — `child_id` is the buyer |
| `taskmate_reward_approved` | `child_id`, `child_name`, `reward_id`, `reward_name`, `claim_id`, `cost`, `recipient_id` (a gift only), `timestamp` |
| `taskmate_reward_rejected` | `child_id`, `child_name`, `reward_id`, `reward_name`, `claim_id`, `reason` (v6.0.0), `timestamp` |

`claim_id` is the same across all three reward events, so a claim can be followed from request to outcome — see [External Lock-Screen Shops](External-Lock-Screen-Shops.md). Since v6.0.0, redeeming a [wish](Wishlist.md) runs through these same events, with an extra `wish_id`.

### Streaks, badges & gamification

| Event | Data fields |
|-------|-------------|
| `taskmate_streak_updated` | `child_id`, `current_streak`, `best_streak`, `timestamp` |
| `taskmate_badge_earned` | `child_id`, `badge_id`, `awarded_id`, `name`, `icon`, `tier` |
| `taskmate_level_up` | `child_id`, `child_name`, `level`, `timestamp` |
| `taskmate_celebration` | `child_id`, `child_name`, `kind`, `tier` (1–3), `message`, `timestamp` (+ event-specific extras, e.g. `level`) |
| `taskmate_quest_completed` | `child_id`, `child_name`, `quest_id`, `quest_name`, `bonus`, `timestamp` |
| `taskmate_challenge_completed` | `child_id`, `child_name`, `challenge_id`, `challenge_name`, `scope`, `bonus`, `timestamp` |

### Mandatory chores

| Event | Data fields |
|-------|-------------|
| `taskmate_mandatory_missed` | `miss_id`, `chore_id`, `child_id`, `period_id`, `penalty_points`, `timestamp` |
| `taskmate_mandatory_penalty_applied` | `miss_id`, `chore_id`, `child_id`, `points`, `timestamp` |
| `taskmate_mandatory_postponed` | `miss_id`, `chore_id`, `child_id`, `next_period`, `timestamp` |
| `taskmate_mandatory_dismissed` | `miss_id`, `chore_id`, `child_id`, `timestamp` |

### Allowance, goals & seasons

| Event | Data fields |
|-------|-------------|
| `taskmate_allowance_paid` | `child_id`, `child_name`, `points`, `month`, `timestamp` |
| `taskmate_family_goal_reached` | `goal_name`, `goal_reward`, `target`, `timestamp` |
| `taskmate_season_champion` | `month`, `child_id`, `child_name`, `points`, `timestamp` |

### Undo

| Event | Data fields |
|-------|-------------|
| `taskmate_chore_approval_undone` | `child_id`, `child_name`, `chore_id`, `chore_name`, `completion_id`, `timestamp` |

### v5.0.0 events

| Event | Data fields |
|-------|-------------|
| `taskmate_chore_expired` | `chore_id`, `chore_name`, `deadline_at`, `timestamp` — a [reactive chore](Reactive-Chores.md) passed its deadline |
| `taskmate_roulette_spun` | `child_id`, `child_name`, `chore_id`, `chore_name`, `multiplier`, `timestamp` — see [Chore Roulette](Chore-Roulette.md) |
| `taskmate_unlock_started` | `entity_id`, `reward_id`, `reward_name`, `child_id`, `child_name`, `started_at`, `revert_at` — see [Timed Unlock Rewards](Timed-Unlock-Rewards.md) |
| `taskmate_unlock_ended` | same fields as `taskmate_unlock_started`, fired when the timer reverts the entity |
| `taskmate_scheduled_change_applied` | `change_id`, `chore_id`, `chore_name`, `changes`, `timestamp` — see [Scheduled Config Changes](Scheduled-Config-Changes.md) |
| `taskmate_guest_archived` | `child_id`, `child_name`, `expired_on`, `timestamp` — see [Guest Child Profiles](Guest-Child-Profiles.md) |
| `taskmate_read_aloud` | `child_id`, `media_player`, `tts_entity`, `message` — see [Read Aloud](Read-Aloud.md) |

### v6.0.0 events

Grouped the same way as the release notes. Every event carries a `timestamp` unless noted.

**Chores and streaks**

| Event | Data fields |
|-------|-------------|
| `taskmate_tag_completion` | `tag_id`, `device_id`, `child_id`, `child_name`, `chore_id`, `chore_name`, `completion_id`, `pending_approval` (no `timestamp`) — a chore was completed by scanning an [NFC tag or QR code](NFC-Tag-Completion.md) |
| `taskmate_team_chore_joined` | `child_id`, `child_name`, `chore_id`, `chore_name`, `joined`, `team_size` (no `timestamp`) — a child joined a [teamwork chore](Teamwork-Chores.md) that isn't full yet |
| `taskmate_team_chore_completed` | `chore_id`, `chore_name`, `child_ids`, `team_size` (no `timestamp`) — the team filled up and everyone got a completion |
| `taskmate_chore_undone` | `child_id`, `child_name`, `chore_id`, `chore_name`, `completion_id`, `timestamp` — a child took back their own chore inside the [undo window](Child-Undo-Window.md) (a parent's rejection fires `taskmate_chore_rejected` instead) |
| `taskmate_streak_freeze_used` | `child_id`, `child_name`, `date`, `streak`, `freezes_left`, `timestamp` — a [streak freeze](Streak-Freezes.md) token saved the streak on `date` |

**Recaps**

| Event | Data fields |
|-------|-------------|
| `taskmate_recap_ready` | `child_id`, `child_name`, `count`, `recaps`, `recipients` (no `timestamp`) — one per child when new [recaps](Recaps.md) are announced at the send time. Fires even when the Recap ready notification is off |

**Bounties** — see [Bounty Board](Bounty-Board.md)

| Event | Data fields |
|-------|-------------|
| `taskmate_bounty_posted` | `bounty_id`, `title`, `points` (no `timestamp`) |
| `taskmate_bounty_updated` | `bounty_id`, `title`, `points`, `claimed_by` (no `timestamp`) |
| `taskmate_bounty_removed` | `bounty_id`, `title` (no `timestamp`) |
| `taskmate_bounty_claimed` | `bounty_id`, `title`, `points`, `child_id`, `child_name`, `timestamp` — a child claimed it |
| `taskmate_bounty_given_back` | same fields — the child handed it back to the board |
| `taskmate_bounty_released` | same fields — a parent put a claimed bounty back on the board |
| `taskmate_bounty_claim_lapsed` | same fields — the claim ran out before the job was finished |
| `taskmate_bounty_completed` | same fields — the child marked it done; it is now waiting for approval |
| `taskmate_bounty_approved` | same fields — a parent approved the finished job |
| `taskmate_bounty_rejected` | same fields — a parent rejected it; the bounty goes back to the same child |
| `taskmate_bounty_withdrawn` | same fields — the child took back their submission |
| `taskmate_bounty_expired` | same fields (empty `child_id`) — an unclaimed bounty passed its expiry |

A finished bounty also fires the usual `taskmate_chore_completed`, with the bounty ID as `chore_id` and an extra `bounty_id`.

**Wishes** — see [Wishlist](Wishlist.md)

All wish events carry `wish_id`, `wish_name`, `child_id`, `child_name`, `target`, `saved`, `pledged` and `timestamp`.

| Event | Extra fields / when |
|-------|---------------------|
| `taskmate_wish_added` | A child added a wish |
| `taskmate_wish_approved` | A parent approved it as a savings goal |
| `taskmate_wish_declined` | A parent declined it |
| `taskmate_wish_pledged` | `points`, `pledger` — someone pledged points towards it |
| `taskmate_wish_saved` | `points` — the child moved points into it |

**Inspections** — see [Surprise Inspections](Surprise-Inspections.md)

All inspection events carry `inspection_id`, `completion_id`, `child_id`, `child_name`, `chore_id`, `chore_name`, `bonus`, `status` and `timestamp`.

| Event | Extra fields / when |
|-------|---------------------|
| `taskmate_inspection_started` | A parent (or the daily pick) started one |
| `taskmate_inspection_passed` | It passed and the bonus was paid |
| `taskmate_inspection_failed` | `redo` — it didn't pass; `redo` is `true` when the chore was sent back |
| `taskmate_inspection_expired` | Nobody decided before the window closed |
| `taskmate_inspection_cancelled` | A parent called it off |
| `taskmate_inspection_reopened` | A pass bonus was undone while the window was still open, so the inspection is open again |

**Auctions** — see [Chore Auctions](Chore-Auctions.md)

All auction events carry `auction_id`, `chore_id`, `chore_name`, `occurrence` (the chore's date), `max_points`, `bid_count`, `child_id`, `child_name` and `timestamp`. They **never** include what anyone bid.

| Event | Extra fields / when |
|-------|---------------------|
| `taskmate_auction_opened` | An auction opened (`child_id` empty) |
| `taskmate_auction_bid` | A child placed or changed a bid |
| `taskmate_auction_bid_withdrawn` | A child withdrew their bid |
| `taskmate_auction_closed` | `price` — bidding closed; `child_id` is the winner (empty when nobody bid) and `price` the winning price |
| `taskmate_auction_cancelled` | The auction was cancelled (`child_id` empty) |

> Since v6.1.0 each of these events fires once. When the matching notification is also sent, the notification system fires a separate `taskmate_<type>_notification` event (e.g. `taskmate_bounty_posted_notification`) carrying the `recipients` list. See [Notifications](Notifications.md#bus-events).

> Notification-type events (`taskmate_pending_chore_approval`, `taskmate_badge_earned_notification`, `taskmate_weekly_digest`, …) carry an extra `recipients` list and are documented in [Notifications](Notifications.md#bus-events).

### v7.0.0 events

| Event | Data fields |
|-------|-------------|
| `taskmate_chore_auto_approved` | `child_id`, `child_name`, `chore_id`, `chore_name`, `points`, `hours`, `timestamp` — a chore nobody reviewed within `hours` approved itself. See [Auto-Approve](Auto-Approve.md). The usual `taskmate_chore_approved` fires as well |
| `taskmate_help_requested` | `child_id`, `child_name`, `chore_id`, `chore_name`, `message`, `message_text`, `request_id`, `recipients` (no `timestamp`) — a child tapped "I'm stuck". Pass `request_id` to `taskmate.answer_help`. See [Help Requests](Help-Requests.md) |
| `taskmate_mood_logged` | `child_id`, `child_name`, `mood`, `emoji`, `timestamp` — a child did the end-of-day [mood check-in](Mood-Check-In.md). `mood` is `great`, `good`, `ok`, `sad` or `upset` |
| `taskmate_mood_low` | `child_id`, `child_name`, `mood`, `emoji`, `recipients` (no `timestamp`) — the mood was `sad` or `upset` |
| `taskmate_sick_day` | `child_id`, `child_name`, `date`, `sick`, `timestamp` — a [sick day](Sick-Days.md) was given (`sick: true`) or taken back (`sick: false`) |
| `taskmate_weekly_goal_reached` | `child_id`, `child_name`, `target`, `earned`, `bonus`, `points_name`, `recipients` (no `timestamp`) — a child reached their [weekly goal](Weekly-Goals.md) |
| `taskmate_penalty_redeemed` | `child_id`, `child_name`, `penalty_name`, `chore_name`, `points`, `points_name`, `recipients` (no `timestamp`) — a child did the [make-it-right](Make-It-Right-Penalties.md) chore and earned `points` back |
| `taskmate_raffle_won` | `child_id`, `child_name`, `raffle_id`, `raffle_name`, `prize`, `tickets`, `timestamp` — the winner of a [raffle](Raffles.md); `tickets` is how many they held |
| `taskmate_raffle_drawn` | `raffle_id`, `raffle_name`, `prize`, `winner_id`, `winner_name`, `tickets`, `recipients` (no `timestamp`) — a raffle was drawn; `tickets` is the total in the draw. Fires even when nobody entered (`winner_id` empty) |
| `taskmate_reward_delivered` | `child_id`, `child_name`, `reward_id`, `reward_name`, `claim_id`, `delivered_by` (`parent` / `child`), `timestamp` — (v7.1.0) a redeemed reward was handed over. See [Reward Fulfilment](Reward-Fulfilment.md) |
| `taskmate_reward_owed` | `child_id`, `child_name`, `reward_id`, `reward_name`, `claim_id`, `days`, `points_name`, `recipients` (no `timestamp`) — (v7.1.0) the reminder that a reward is still owed went out |
| `taskmate_appeal_submitted` | `appeal_id`, `child_id`, `child_name`, `kind`, `item_name`, `points`, `message`, `timestamp` — (v7.1.0) a child [appealed](Appeals.md) a rejection or penalty |
| `taskmate_appeal_decided` | The same plus `overturned` and `note` — (v7.1.0) a parent decided an appeal |
| `taskmate_boost_started` | `id`, `name`, `multiplier`, `chore_ids`, `child_ids`, `starts_at`, `ends_at`, `minutes`, `rule_id` (recurring only), `timestamp` — (v7.1.0) a [boost](Boost-Windows.md) went live |
| `taskmate_boost_ended` | The same plus `ended_early` — (v7.1.0) a boost ran out or was ended |
| `taskmate_screen_time_changed` | `child_id`, `child_name`, `delta`, `minutes`, `reward_id` (from a reward only), `timestamp` — a child's [screen-time](Screen-Time-Bank.md) balance went up or down |
| `taskmate_screen_time_low` | `child_id`, `child_name`, `minutes`, `timestamp` — the balance reached the warning level. The notification's own event is `taskmate_screen_time_low_notification` |
| `taskmate_screen_time_out` | `child_id`, `child_name`, `minutes`, `timestamp` — the balance ran out. The notification's own event is `taskmate_screen_time_out_notification` |
| `taskmate_points_expiring` | `child_id`, `child_name`, `points`, `date`, `timestamp` — some of a child's points enter the warning window before [expiring](Points-Expiry.md) on `date`. The notification's own event is `taskmate_points_expiring_notification` |
| `taskmate_points_expired` | `child_id`, `child_name`, `points`, `timestamp` — unspent points [expired](Points-Expiry.md) |
| `taskmate_reward_rated` | `child_id`, `child_name`, `reward_id`, `reward_name`, `claim_id`, `rating` (1–3), `timestamp` — a child [rated a reward](Reward-Extras.md#rate-the-reward) they had |
| `taskmate_penalty_warning` | `child_id`, `child_name`, `penalty_id`, `penalty_name`, `points`, `resets` (`daily` / `weekly`), `timestamp` — a [warn-first penalty](Penalty-Warnings.md) gave its warning instead of taking points |
| `taskmate_sibling_check` | `child_id` and `child_name` (the checker), `checked_child_id`, `checked_child_name`, `chore_id`, `chore_name`, `completion_id`, `verdict` (`done` / `not_yet`), `bonus`, `note` (not yet only, when given), `timestamp` — a [sibling check](Sibling-Checks.md). A `done` also fires `taskmate_chore_approved` with `checked_by` |
| `taskmate_bin_day` | `chore_id`, `chore_name`, `bin`, `kind` (`put_out` / `bring_in`), `child_ids`, `timestamp` — a [bin-day chore](Bin-Day-Chores.md) was added |
| `taskmate_screen_time_saved` | `child_id`, `child_name`, `minutes`, `jar`, `balance`, `timestamp` — a child put minutes in their [screen-time jar](Screen-Time-Bank.md#weekend-jar) |
| `taskmate_screen_time_jar_opened` | `child_id`, `child_name`, `minutes`, `balance`, `timestamp` — the jar opened and its minutes joined the balance. The notification's own event is `taskmate_screen_time_jar_opened_notification` |
| `taskmate_shopping_job` | `kind` (`added` / `done` / `removed`), `chore_id`, `chore_name`, `item_uid`, `child_ids`, `timestamp` — a [shopping-list job](Shopping-List-Jobs.md) was raised, ticked off, or dropped because its item left the list |
| `taskmate_personal_best` | `child_id`, `child_name`, `record`, `value`, `previous`, `date`, `timestamp` — (v7.1.0) a child beat one of their own records. `record` is `longest_streak`, `best_day_points`, `best_day_chores`, `best_week_points` or `best_single_award`. See [Personal Bests](Personal-Bests.md). The notification's own event is `taskmate_personal_best_notification` |
| `taskmate_pet_evolved` | `child_id`, `child_name`, `pet_name`, `species`, `kind`, `news`, `recipients` (no `timestamp`), plus `pet_level` when `kind` is `level` — a [virtual pet](Virtual-Pets.md) reached something new. `kind` is `stage`, `legendary`, `egg` or `level`; `news` is the ready-made sentence |

The events with a `recipients` list come from the notification system and fire whether or not the matching notification is switched on (`recipients` is then empty). See [Notifications](Notifications.md#bus-events).

#### Event entities

Since v7.0.0 the same moments are also published as **event entities**: one per child (`event.taskmate_<child>_activity`) and one for the family (`event.taskmate_family_activity`). They make TaskMate moments pickable in the UI automation editor without typing an event name ("When Malia's activity has event type chore_approved"), and show the latest moment on a dashboard. See [Event Entities](Event-Entities.md).

### Example — react to a celebration with lights

The `taskmate_celebration` event carries a `tier` (1 = small, 2 = medium, 3 = epic) so a single automation can scale its reaction to the size of the moment.

```yaml
alias: TaskMate — Celebrate big moments
triggers:
  - trigger: event
    event_type: taskmate_celebration
conditions:
  - condition: template
    value_template: "{{ trigger.event.data.tier >= 3 }}"
actions:
  - action: light.turn_on
    target:
      entity_id: light.living_room
    data:
      effect: rainbow
  - action: notify.mobile_app_johns_phone
    data:
      title: "🎉 TaskMate"
      message: "{{ trigger.event.data.message }}"
```

### Example — log every penalty

```yaml
alias: TaskMate — Log penalties
triggers:
  - trigger: event
    event_type: taskmate_penalty_applied
actions:
  - action: logbook.log
    data:
      name: TaskMate
      message: >
        {{ trigger.event.data.child_name }} lost
        {{ trigger.event.data.points }} for "{{ trigger.event.data.penalty_name }}"
```

---

## Blueprint Pack

TaskMate ships a set of ready-made Home Assistant **automation blueprints** so you can react to the most common TaskMate moments without writing the trigger and condition logic yourself. Each blueprint fires on a TaskMate bus event and lets you pick the action to run — flash a light, play a sound, announce on a speaker, run a scene, send a notification, and so on.

| Blueprint | Fires on | Use it for | Inputs |
|-----------|----------|-----------|--------|
| `chore_completed.yaml` | `taskmate_chore_completed` | Reward a completed chore — flash a light, play a chime, post a message | **Only this child** (optional name to restrict to one child; blank = all) and your **Action** |
| `level_up.yaml` | `taskmate_level_up` | Celebrate when a child reaches a new XP level | **Only this child** (optional) and your **Action** |
| `reward_approved.yaml` | `taskmate_reward_approved` | React when a reward claim is approved — announce it, unlock a smart plug for the games console | **Only this child** (optional) and your **Action** |
| `mandatory_missed.yaml` | `taskmate_mandatory_missed` | React when a mandatory chore's time window closes incomplete — pause the TV, turn a light red, alert a parent | Your **Action** (fires for every child) |

The first three accept an optional **Only this child** name: leave it blank to react to every child, or enter a child's exact name to restrict the automation to them. `mandatory_missed` has no child filter — it runs for any missed mandatory chore. (For more control, you can still build your own automation off these events directly — see [Bus Events Reference](#bus-events-reference) above.)

### Importing a blueprint

In Home Assistant, go to **Settings → Automations & scenes → Blueprints → Import blueprint**, then paste the raw URL of the blueprint you want, for example:

```
https://github.com/tempus2016/taskmate/blob/main/blueprints/automation/taskmate/chore_completed.yaml
```

Then choose **Create automation → (the imported blueprint)**, optionally set the child name, and pick your action.

### Event data in your action

The triggering event is available to your action's templates as `trigger.event.data`:

| Blueprint event | Available fields |
|-----------------|------------------|
| `taskmate_chore_completed` | `child_name`, `chore_name`, `points`, `difficulty` |
| `taskmate_level_up` | `child_name`, `level` |
| `taskmate_reward_approved` | `child_name`, `reward_name`, `cost` |
| `taskmate_mandatory_missed` | `child_id`, `chore_id`, `period_id`, `penalty_points` |

For example, an action that announces who finished what:

```yaml
service: notify.mobile_app_johns_phone
data:
  message: "{{ trigger.event.data.child_name }} finished {{ trigger.event.data.chore_name }}!"
```

---

## Example Automations

---

## Notify Parents When Approvals Are Pending

> **Note:** TaskMate v1.1.3+ has built-in notification support. Configure a notify service in the **TaskMate** panel → **Notifications** for simple per-chore alerts. Use the automation below for more control — multiple recipients, conditions, custom messages, scheduling.

Send a push notification to the parent's phone when a chore is waiting for approval.

```yaml
alias: TaskMate — Notify on pending approval
trigger:
  - platform: state
    entity_id: binary_sensor.taskmate_has_pending_approvals
    to: "on"
action:
  - service: notify.mobile_app_johns_phone
    data:
      title: "TaskMate ✅"
      message: >
        {{ state_attr('binary_sensor.taskmate_has_pending_approvals', 'pending_chore_completions') }}
        chore(s) and
        {{ state_attr('binary_sensor.taskmate_has_pending_approvals', 'pending_reward_claims') }}
        reward claim(s) awaiting approval.
      data:
        url: /lovelace/parent-dashboard
```

---

## Remind Child to Complete Chores

Send a reminder if a child hasn't completed any chores by a certain time.

```yaml
alias: TaskMate — Evening chore reminder
trigger:
  - platform: time
    at: "18:00:00"
condition:
  - condition: template
    value_template: >
      {% set children = state_attr('sensor.taskmate_overview', 'children') %}
      {% set child = children | selectattr('name', 'eq', 'Malia') | first %}
      {{ child.pending_points == 0 and child.points == child.points }}
      {# Simpler: check if done_today from todays_completions #}
action:
  - service: notify.mobile_app_malias_tablet
    data:
      title: "Don't forget your chores! 🌟"
      message: "You still have chores to do today. Check your chore list!"
```

---

## Award Bonus Points for Good Behaviour

Use an input_button or a script to quickly award bonus points.

```yaml
# input_button.yaml
input_button:
  malia_bonus:
    name: "Award Malia Bonus Points"
    icon: mdi:star-plus

# automation.yaml
alias: TaskMate — Award bonus on button press
trigger:
  - platform: state
    entity_id: input_button.malia_bonus
action:
  - service: taskmate.add_points
    data:
      child_id: a8c8376a
      points: 5
      reason: "Good behaviour bonus"
```

---

## Weekly Summary Notification

Send a weekly summary of each child's activity every Sunday evening.

```yaml
alias: TaskMate — Weekly summary
trigger:
  - platform: time
    at: "19:00:00"
condition:
  - condition: time
    weekday:
      - sun
action:
  - service: notify.mobile_app_johns_phone
    data:
      title: "TaskMate Weekly Summary 📊"
      message: >
        {% set children = state_attr('sensor.taskmate_overview', 'children') %}
        {% for child in children %}
        {{ child.name }}: {{ child.points }} pts | {{ child.current_streak }} day streak
        {% endfor %}
```

---

## Complete a Chore via NFC Tag

> **Since v6.0.0 this is built in.** Link tags to a chore in the chore editor under **More options → NFC / QR tags**, and TaskMate works out which child scanned. See [NFC Tag Completion](NFC-Tag-Completion.md). The automation below is still useful if you want to do something extra on a scan, such as sending a message.

Tap an NFC tag to automatically complete a chore without opening the app.

```yaml
alias: TaskMate — NFC complete Make Bed
trigger:
  - platform: tag
    tag_id: "your-nfc-tag-id-here"
action:
  - service: taskmate.complete_chore
    data:
      chore_id: b3f9a12c
      child_id: a8c8376a
  - service: notify.mobile_app_malias_tablet
    data:
      title: "Chore completed! ⭐"
      message: "Make Bed marked as done. +5 Stars!"
```

---

## Complete a Chore When a Smart Device is Used

Use a smart plug or presence sensor to automatically complete a chore.

**Example: Brushing teeth — complete when bathroom motion detected at the right time:**

```yaml
alias: TaskMate — Auto complete brush teeth
trigger:
  - platform: state
    entity_id: binary_sensor.bathroom_motion
    to: "on"
condition:
  - condition: time
    after: "07:00:00"
    before: "08:30:00"
  - condition: time
    weekday:
      - mon
      - tue
      - wed
      - thu
      - fri
action:
  - service: taskmate.complete_chore
    data:
      chore_id: brush_teeth_chore_id
      child_id: a8c8376a
```

---

## Daily Streak Reminder

Remind a child if they haven't completed a chore today and their streak is at risk.

```yaml
alias: TaskMate — Streak risk reminder
trigger:
  - platform: time
    at: "20:00:00"
condition:
  - condition: template
    value_template: >
      {% set children = state_attr('sensor.taskmate_overview', 'children') %}
      {% set child = children | selectattr('name', 'eq', 'Malia') | first %}
      {% set today_completions = state_attr('sensor.taskmate_overview', 'todays_completions') | selectattr('child_id', 'eq', child.id) | list %}
      {{ today_completions | length == 0 and child.current_streak > 0 }}
action:
  - service: notify.mobile_app_malias_tablet
    data:
      title: "🔥 Your streak is at risk!"
      message: >
        {% set children = state_attr('sensor.taskmate_overview', 'children') %}
        {% set child = children | selectattr('name', 'eq', 'Malia') | first %}
        You have a {{ child.current_streak }} day streak! Complete a chore before midnight to keep it going.
```

---

## Display Pending Approvals on a Dashboard Badge

Show a badge on your parent dashboard that turns red when approvals are pending.

```yaml
# In your dashboard YAML
- type: entity
  entity: sensor.taskmate_pending_approvals
  name: Pending
  icon: mdi:clipboard-clock
  state_color: true
```

Or use a conditional card to show a banner:

```yaml
- type: conditional
  conditions:
    - entity: binary_sensor.taskmate_has_pending_approvals
      state: "on"
  card:
    type: markdown
    content: >
      ## ⚠️ {{ states('sensor.taskmate_pending_approvals') }} item(s) need your attention
    card_mod:
      style: |
        ha-card {
          background: var(--warning-color);
          color: white;
        }
```

---

## Auto-Approve Chores After a Timeout

> **Since v7.0.0 this is built in.** Set **Settings → Auto-approve after (hours)** instead; it approves at the points the child was promised, leaves open-ended chores and bounties for you, and fires `taskmate_chore_auto_approved`. See [Auto-Approve](Auto-Approve.md). The automation below still works if you want different rules.

Automatically approve all pending completions if the parent hasn't approved after 24 hours.

```yaml
alias: TaskMate — Auto approve after 24h
trigger:
  - platform: time_pattern
    hours: "/1"
condition:
  - condition: template
    value_template: >
      {{ state_attr('sensor.taskmate_pending_approvals', 'chore_completions') | length > 0 }}
action:
  - repeat:
      for_each: >
        {{ state_attr('sensor.taskmate_pending_approvals', 'chore_completions') |
           selectattr('completed_at', 'lt', (now() - timedelta(hours=24)).isoformat()) |
           list }}
      sequence:
        - service: taskmate.approve_chore
          data:
            completion_id: "{{ repeat.item.completion_id }}"
```

---

## Jinja2 Template Examples

Useful templates for dashboard cards and automations.

**Get a specific child's points:**
```jinja2
{% set children = state_attr('sensor.taskmate_overview', 'children') %}
{% set child = children | selectattr('name', 'eq', 'Malia') | first %}
{{ child.name }} has {{ child.points }} {{ state_attr('sensor.taskmate_overview', 'points_name') }}
```

**List all children and their streaks:**
```jinja2
{% set children = state_attr('sensor.taskmate_overview', 'children') %}
{% for child in children %}
  {{ child.name }}: {{ child.current_streak }} day streak
{% endfor %}
```

**Check if any child has a pending claim:**
```jinja2
{{ state_attr('binary_sensor.taskmate_has_pending_approvals', 'pending_reward_claims') > 0 }}
```

**Get today's completions for a specific child:**
```jinja2
{% set completions = state_attr('sensor.taskmate_overview', 'todays_completions') %}
{% set child_completions = completions | selectattr('child_id', 'eq', 'a8c8376a') | list %}
{{ child_completions | length }} chores done today
```

See also [Watch Complications](Watch-Complications.md) — templates for Apple Watch and Wear OS built on the per-child watch sensor.
