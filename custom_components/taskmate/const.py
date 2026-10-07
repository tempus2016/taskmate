"""Constants for TaskMate integration."""

import re
from typing import Final

DOMAIN: Final = "taskmate"

CONF_TASK_GROUP_ID: Final = "group_id"
CONF_TASK_GROUP_NAME: Final = "name"
CONF_TASK_GROUP_POLICY: Final = "policy"
CONF_TASK_GROUP_CHORE_IDS: Final = "chore_ids"
TASK_GROUP_POLICIES: Final = ["sticky", "spread"]

# Calendar projection: how many days ahead each chore's assignment is pushed
# into the configured HA calendars. 14 days balances planning visibility with
# calendar noise; raise via the Settings flow for longer planning horizons.
DEFAULT_CALENDAR_PROJECTION_DAYS: Final = 14
MIN_CALENDAR_PROJECTION_DAYS: Final = 1
MAX_CALENDAR_PROJECTION_DAYS: Final = 90

# Assignment modes
# "everyone"    = visible to every child in assigned_to (or all children if empty) -- existing behavior
# "alternating" = round-robin through assigned_to (or all children), one child per calendar day
# "random"      = deterministic per-day random pick from the same pool (each chore picks independently)
# "balanced"    = split today's balanced-mode chores evenly across the pool so no one child gets swamped
# "first_come"  = competitive: shown to the whole pool at once; first child to complete it wins and it
#                 hides for everyone else (shared quota of 1). A parent rejection reopens it for the pool.
ASSIGNMENT_MODES: Final = ["everyone", "alternating", "random", "balanced", "first_come", "unassigned"]

# Teamwork chores (#928): how a finished team's points are shared out.
# "each"  = every participant earns the chore's full points
# "split" = the points are divided evenly across the team, rounded down
TEAM_POINTS_MODES: Final = ["each", "split"]
# Upper bound on team_size — more than a family has children is meaningless,
# and the joins list rides in a sensor attribute.
TEAM_SIZE_MAX: Final = 10

# Bounty board (#931): one-off jobs any eligible child can claim.
# A claim locks the bounty to one child for claim_hours (never past its
# expiry); an unfinished claim lapses back onto the board.
BOUNTY_STATUSES: Final = ["open", "claimed", "pending", "completed", "expired"]
BOUNTY_CLAIM_HOURS_DEFAULT: Final = 2
BOUNTY_CLAIM_HOURS_MAX: Final = 48
BOUNTY_POINTS_MAX: Final = 100000
BOUNTY_TITLE_MAX_LENGTH: Final = 120
BOUNTY_DESCRIPTION_MAX_LENGTH: Final = 500
# The claimer is warned this long before their claim lapses (opt-in type).
BOUNTY_LAPSE_WARNING_MINUTES: Final = 15
# Approved bounties stay on the card as "Recently completed" this long.
BOUNTY_RECENT_HOURS: Final = 24

# Chore auctions (#982): children bid the fewest points they'd accept for one
# occurrence of a chore; the lowest bid wins it at that price.
AUCTION_STATUSES: Final = ["open", "closed", "cancelled"]
AUCTION_POINTS_MAX: Final = 100000
# Eligible children get the "closing soon" push this long before bidding ends.
AUCTION_REMINDER_MINUTES: Final = 60
# Closed auctions stay on the children's cards as results this long.
AUCTION_RESULTS_HOURS: Final = 24

# Default values
DEFAULT_POINTS_NAME: Final = "Stars"
DEFAULT_POINTS_ICON: Final = "mdi:star"

# Schedule modes
SCHEDULE_MODES: Final = ["specific_days", "recurring", "one_shot"]

# Nominal length of each Mode-B recurrence period, in days. Used for report
# expectations and recurrence math (not for the shorter availability window
# in coord_chores.is_chore_available_for_child, which is deliberately capped).
RECURRENCE_PERIOD_DAYS: Final = {
    "every_2_days": 2,
    "weekly": 7,
    "every_2_weeks": 14,
    "monthly": 30,
    "every_3_months": 91,
    "every_6_months": 182,
}

# Custom "every N days" recurrences (#1038) are stored as ``every_<N>_days``;
# the original every_2_days is simply the N=2 case. N is bounded so a typo
# can't park a chore for years.
MIN_RECURRENCE_INTERVAL_DAYS: Final = 2
MAX_RECURRENCE_INTERVAL_DAYS: Final = 365
_EVERY_N_DAYS_RE: Final = re.compile(r"every_(\d{1,3})_days")


def recurrence_interval_days(recurrence: str | None) -> int | None:
    """N for an ``every_<N>_days`` recurrence, else None (also when N is out of range)."""
    match = _EVERY_N_DAYS_RE.fullmatch(recurrence) if isinstance(recurrence, str) else None
    if not match:
        return None
    days = int(match.group(1))
    return days if MIN_RECURRENCE_INTERVAL_DAYS <= days <= MAX_RECURRENCE_INTERVAL_DAYS else None


def recurrence_period_days(recurrence: str | None) -> int:
    """Nominal period of a Mode-B recurrence in days (weekly when unknown)."""
    return recurrence_interval_days(recurrence) or RECURRENCE_PERIOD_DAYS.get(recurrence or "", 7)


# Badge tiers, lowest to highest.
BADGE_TIERS: Final = ["bronze", "silver", "gold", "platinum"]

# Time categories for chores
TIME_CATEGORIES: Final = [
    "morning",
    "afternoon",
    "evening",
    "night",
    "anytime",
]

# Time category icons
TIME_CATEGORY_ICONS: Final = {
    "morning": "mdi:weather-sunny",
    "afternoon": "mdi:white-balance-sunny",
    "evening": "mdi:weather-sunset",
    "night": "mdi:weather-night",
    "anytime": "mdi:clock-outline",
}

# Default user-editable time-of-day periods. "anytime" is implicit (all-day,
# always available) and never appears in this list. An empty label means
# "use the translated built-in name for this id".
DEFAULT_TIME_PERIODS: Final = [
    {"id": "morning", "label": "", "start": "06:00", "end": "12:00", "icon": "mdi:weather-sunny"},
    {"id": "afternoon", "label": "", "start": "12:00", "end": "17:00", "icon": "mdi:white-balance-sunny"},
    {"id": "evening", "label": "", "start": "17:00", "end": "21:00", "icon": "mdi:weather-sunset"},
    {"id": "night", "label": "", "start": "21:00", "end": "23:59", "icon": "mdi:weather-night"},
]

MAX_TIME_PERIODS: Final = 24

# Open-ended chores (#832): the child describes the work and suggests what it
# was worth. Both are child-entered free input, so they're bounded before storage.
CHORE_NOTE_MAX_LENGTH: Final = 200

# Admin panel Today page (#966): days of per-child done/total snapshots kept.
DAILY_PROGRESS_KEEP_DAYS: Final = 30
CHORE_SUGGESTED_POINTS_MAX: Final = 999

# NFC / QR tag completion (#923): a chore lists the HA tag ids that complete it.
# Tag ids are typed or picked by a parent, so both the count and the length are
# bounded before storage.
MAX_CHORE_TAGS: Final = 10
TAG_ID_MAX_LENGTH: Final = 100
# A phone reading an NFC sticker often fires tag_scanned twice for one tap, so a
# second scan of the same chore by the same child inside this window is ignored
# even when the daily limit would allow another completion.
TAG_SCAN_DEBOUNCE_SECONDS: Final = 60
EVENT_TAG_COMPLETION: Final = "taskmate_tag_completion"

# Platforms
PLATFORMS: Final = ["sensor", "button", "binary_sensor"]

# Services
SERVICE_COMPLETE_CHORE: Final = "complete_chore"
SERVICE_APPROVE_CHORE: Final = "approve_chore"
SERVICE_APPROVE_ALL_CHORES: Final = "approve_all_chores"
SERVICE_REJECT_CHORE: Final = "reject_chore"
SERVICE_UNDO_CHORE: Final = "undo_chore"
SERVICE_UNDO_CHORE_APPROVAL: Final = "undo_chore_approval"
SERVICE_APPLY_MANDATORY_PENALTY: Final = "apply_mandatory_penalty"
SERVICE_POSTPONE_MANDATORY_CHORE: Final = "postpone_mandatory_chore"
SERVICE_DISMISS_MANDATORY_CHORE: Final = "dismiss_mandatory_chore"
SERVICE_CLAIM_REWARD: Final = "claim_reward"
SERVICE_APPROVE_REWARD: Final = "approve_reward"
SERVICE_REJECT_REWARD: Final = "reject_reward"
SERVICE_ADD_POINTS: Final = "add_points"
SERVICE_REMOVE_POINTS: Final = "remove_points"
SERVICE_UNDO_TRANSACTION: Final = "undo_transaction"
SERVICE_TEST_NOTIFICATION: Final = "test_notification"
SERVICE_GIFT_POINTS: Final = "gift_points"
SERVICE_ADJUST_STREAK_FREEZES: Final = "adjust_streak_freezes"
SERVICE_RECORD_ALLOWANCE_PAYOUT: Final = "record_allowance_payout"
SERVICE_REQUEST_SWAP: Final = "request_swap"
SERVICE_SPIN_ROULETTE: Final = "spin_roulette"
SERVICE_READ_ALOUD: Final = "read_aloud"
SERVICE_CHOOSE_AVATAR: Final = "choose_avatar"
SERVICE_SET_CHORE_ORDER: Final = "set_chore_order"
SERVICE_PREVIEW_SOUND: Final = "preview_sound"
SERVICE_ADD_PENALTY: Final = "add_penalty"
SERVICE_UPDATE_PENALTY: Final = "update_penalty"
SERVICE_REMOVE_PENALTY: Final = "remove_penalty"
SERVICE_APPLY_PENALTY: Final = "apply_penalty"
SERVICE_ADD_BONUS: Final = "add_bonus"
SERVICE_UPDATE_BONUS: Final = "update_bonus"
SERVICE_REMOVE_BONUS: Final = "remove_bonus"
SERVICE_APPLY_BONUS: Final = "apply_bonus"
SERVICE_ADD_CHORE: Final = "add_chore"
SERVICE_ALLOCATE_POINTS_TO_POOL: Final = "allocate_points_to_pool"
SERVICE_SKIP_CHORE: Final = "skip_chore"
SERVICE_SET_CHORE_MANUAL_START: Final = "set_chore_manual_start"
SERVICE_ADD_TASK_GROUP: Final = "add_task_group"
SERVICE_UPDATE_TASK_GROUP: Final = "update_task_group"
SERVICE_REMOVE_TASK_GROUP: Final = "remove_task_group"
SERVICE_COMPLETE_BONUS_SUBTASK: Final = "complete_bonus_subtask"
SERVICE_START_TIMED_TASK: Final = "start_timed_task"
SERVICE_PAUSE_TIMED_TASK: Final = "pause_timed_task"
SERVICE_STOP_TIMED_TASK: Final = "stop_timed_task"
SERVICE_LEAVE_TEAM_CHORE: Final = "leave_team_chore"
SERVICE_COMPLETE_NEXT_CHORE: Final = "complete_next_chore"
SERVICE_POST_BOUNTY: Final = "post_bounty"
SERVICE_UPDATE_BOUNTY: Final = "update_bounty"
SERVICE_REMOVE_BOUNTY: Final = "remove_bounty"
SERVICE_CLAIM_BOUNTY: Final = "claim_bounty"
SERVICE_GIVE_BACK_BOUNTY: Final = "give_back_bounty"
SERVICE_COMPLETE_BOUNTY: Final = "complete_bounty"

# Events
EVENT_PREVIEW_SOUND: Final = "taskmate_preview_sound"

# Attributes
ATTR_CHILD_ID: Final = "child_id"
ATTR_CHORE_ID: Final = "chore_id"
ATTR_AS_PARENT: Final = "as_parent"
ATTR_REWARD_ID: Final = "reward_id"
ATTR_POINTS: Final = "points"
ATTR_REASON: Final = "reason"
ATTR_CHORE_ORDER: Final = "chore_order"
ATTR_SOUND: Final = "sound"
ATTR_PENALTY_ID: Final = "penalty_id"
ATTR_PENALTY_NAME: Final = "name"
ATTR_PENALTY_POINTS: Final = "points"
ATTR_PENALTY_DESCRIPTION: Final = "description"
ATTR_PENALTY_ICON: Final = "icon"
ATTR_PENALTY_ASSIGNED_TO: Final = "assigned_to"
ATTR_BONUS_ID: Final = "bonus_id"
ATTR_BONUS_NAME: Final = "name"
ATTR_BONUS_POINTS: Final = "points"
ATTR_BONUS_DESCRIPTION: Final = "description"
ATTR_BONUS_ICON: Final = "icon"
ATTR_BONUS_ASSIGNED_TO: Final = "assigned_to"
ATTR_CHORE_NAME: Final = "name"
ATTR_CHORE_DESCRIPTION: Final = "description"
ATTR_CHORE_POINTS: Final = "points"
ATTR_CHORE_ASSIGNED_TO: Final = "assigned_to"
ATTR_CHORE_TIME_CATEGORY: Final = "time_category"
ATTR_CHORE_ONE_SHOT: Final = "one_shot"
ATTR_CHORE_REQUIRES_APPROVAL: Final = "requires_approval"
ATTR_CHORE_EXPIRES_IN_MINUTES: Final = "expires_in_minutes"
ATTR_CHORE_SPEED_BONUS_POINTS: Final = "speed_bonus_points"
ATTR_BONUS_SUBTASK_ID: Final = "bonus_subtask_id"

# Badge attributes
ATTR_BADGE_ID: Final = "badge_id"
ATTR_BADGE_NAME: Final = "name"
ATTR_BADGE_DESCRIPTION: Final = "description"
ATTR_BADGE_ICON: Final = "icon"
ATTR_BADGE_TIER: Final = "tier"
ATTR_BADGE_POINT_BONUS: Final = "point_bonus"
ATTR_BADGE_CRITERIA: Final = "criteria"
ATTR_BADGE_COMBINATOR: Final = "combinator"
ATTR_BADGE_ASSIGNED_TO: Final = "assigned_to"
ATTR_BADGE_NOTIFY_ON_EARN: Final = "notify_on_earn"
ATTR_BADGE_ENABLED: Final = "enabled"
ATTR_AWARDED_BADGE_ID: Final = "awarded_badge_id"

# Completion sound options
# Most sounds are synthesized via Web Audio API
# Fart sounds are CC0 audio files from BigSoundBank.com and GfxSounds.com
COMPLETION_SOUND_OPTIONS: Final = [
    "none",  # No sound
    "coin",  # Coin collect sound
    "levelup",  # Level up / success sound
    "fanfare",  # Celebratory fanfare
    "chime",  # Simple chime
    "powerup",  # Power up sound
    "undo",  # Sad/descending "womp womp" for undo actions
    "fart1",  # Flatulence 1 (short)
    "fart2",  # Flatulence 2 (short)
    "fart3",  # Flatulence 3 (short)
    "fart4",  # Pony flatulence 2 (~3 sec)
    "fart5",  # Flatulence 4 - discreet (short)
    "fart6",  # Prout'cochons 1 - pig game sound (short)
    "fart7",  # Prout'cochons 2 - pig game sound (short)
    "fart8",  # Prout'cochons 3 - pig game sound (short)
    "fart9",  # Pony flatulence 1 (short)
    "fart10",  # Baby fart (short)
    "fart_random",  # Random fart - picks a random fart sound each time!
]


def is_valid_completion_sound(value: str | None) -> bool:
    """True for a built-in sound name or a well-formed custom sound reference.

    A chore's ``completion_sound`` is either one of ``COMPLETION_SOUND_OPTIONS``
    or ``custom:<32 hex>.<ext>`` pointing at an uploaded file (#856). Kept here
    rather than in ``sounds.py`` so schema code can validate the whole field
    from one import. The custom check is pure, so it is safe on untrusted input.
    """
    if value in COMPLETION_SOUND_OPTIONS:
        return True
    from .sounds import is_custom_sound

    return is_custom_sound(value)


# --- Chore difficulty tiers ---
# Each chore carries a difficulty tier; the points it awards are the base
# points multiplied by the tier's multiplier. "medium" is the neutral baseline
# (×1.0) so chores that predate this feature (which default to medium) keep
# their exact award value. Multipliers are configurable via the settings
# "difficulty_multiplier_<tier>" keys.
DIFFICULTY_TIERS: Final = ("easy", "medium", "hard")
DEFAULT_DIFFICULTY: Final = "medium"
DEFAULT_DIFFICULTY_MULTIPLIERS: Final = {"easy": 0.5, "medium": 1.0, "hard": 2.0}

# Setup wizard age groups (#980), youngest first. A child's age group only
# decides which chores the wizard suggests; "" means none picked. It is stored
# separately from the birthday so an age without a date never becomes a fake
# birthday (which would set off birthday mode on the wrong day).
AGE_GROUPS: Final = ("3_5", "6_8", "9_12", "13_plus")

# --- Chore quality rating (#927) ---
# When the "quality_rating_enabled" setting is on, a parent may rate an approval
# 1-3 stars and the chore's base points are scaled by that star's multiplier
# (configurable via the "quality_rating_multiplier_<n>" settings keys). An
# unrated approval pays 100%, so turning the feature on changes nothing until a
# parent actually picks a star.
QUALITY_RATINGS: Final = (1, 2, 3)
DEFAULT_QUALITY_RATING_MULTIPLIERS: Final = {1: 0.75, 2: 1.0, 3: 1.25}

# --- Notification type IDs (v3.9.0) ---
NOTIF_TYPE_BEDTIME_REMINDER: Final = "bedtime_reminder"
NOTIF_TYPE_STREAK_AT_RISK: Final = "streak_at_risk"
NOTIF_TYPE_ALL_CHORES_DONE: Final = "all_chores_done"
NOTIF_TYPE_BADGE_EARNED: Final = "badge_earned"
NOTIF_TYPE_PENDING_CHORE_APPROVAL: Final = "pending_chore_approval"
NOTIF_TYPE_PENDING_REWARD_CLAIM: Final = "pending_reward_claim"
NOTIF_TYPE_STREAK_MILESTONE: Final = "streak_milestone"
NOTIF_TYPE_LEVEL_UP: Final = "level_up"
NOTIF_TYPE_WEEKLY_DIGEST: Final = "weekly_digest"
NOTIF_TYPE_CELEBRATION: Final = "celebration"
NOTIF_TYPE_MANDATORY_REMINDER: Final = "mandatory_reminder"
NOTIF_TYPE_MANDATORY_PARENT_ALERT: Final = "mandatory_parent_alert"
NOTIF_TYPE_MONTHLY_REPORT: Final = "monthly_report"
NOTIF_TYPE_SEASON_CHAMPION: Final = "season_champion"
NOTIF_TYPE_FAMILY_GOAL_REACHED: Final = "family_goal_reached"
NOTIF_TYPE_BIRTHDAY: Final = "birthday"
NOTIF_TYPE_STREAK_FREEZE_USED: Final = "streak_freeze_used"
NOTIF_TYPE_PRESENCE_ARRIVAL: Final = "presence_arrival"
NOTIF_TYPE_BOUNTY_POSTED: Final = "bounty_posted"
NOTIF_TYPE_BOUNTY_CLAIM_LAPSING: Final = "bounty_claim_lapsing"
NOTIF_TYPE_RECAP_READY: Final = "recap_ready"
# Reject reasons (#976): tells a child a chore or reward claim was sent back,
# with the parent's reason when one was given.
NOTIF_TYPE_ITEM_REJECTED: Final = "item_rejected"
# Chore auctions (#982): an auction opened, bidding closes within the hour,
# and the result (or a cancellation).
NOTIF_TYPE_AUCTION_OPENED: Final = "auction_opened"
NOTIF_TYPE_AUCTION_CLOSING: Final = "auction_closing"
NOTIF_TYPE_AUCTION_RESULT: Final = "auction_result"
# Surprise inspections (#981): the child hears an inspection is coming (only
# when they're told) and that it passed; the parent is reminded 30 minutes
# before an undecided inspection closes.
NOTIF_TYPE_INSPECTION_STARTED: Final = "inspection_started"
NOTIF_TYPE_INSPECTION_PASSED: Final = "inspection_passed"
NOTIF_TYPE_INSPECTION_REMINDER: Final = "inspection_reminder"

# Presence-aware reminders (#926): the default for how long a child must have
# been away before arriving home earns a "you're home" nudge.
DEFAULT_PRESENCE_ARRIVAL_MIN_AWAY: Final = 30

# Default notification tap target. Must match PANEL_URL_PATH in panel.py —
# a bare /taskmate is the static-files prefix and returns 403, not the panel.
DEFAULT_NOTIFICATION_NAV_URL: Final = "/taskmate-admin"

# Default notification group (#811). The HA companion app stacks notifications
# that share this key, so TaskMate's alerts collapse into one bundle instead of
# scattering through the rest of the phone's HA notifications. Applied by
# default — set it to "" in the panel to turn grouping off.
DEFAULT_NOTIFICATION_GROUP: Final = "taskmate"

# --- Wishlist with pledges (#932) ---
# Wishes a child has open at once: waiting for approval, saving, or waiting
# for the parent to hand the thing over.
WISH_MAX_OPEN_PER_CHILD: Final = 5
WISH_MAX_TARGET: Final = 100000
# Pledges on one wish; each is typed by a parent, so this only bounds abuse.
WISH_MAX_PLEDGES: Final = 50
# Finished wishes kept per child: declined ones stay on the card (with the
# reason) until dismissed, redeemed ones are the panel's history.
WISH_KEEP_DECLINED_PER_CHILD: Final = 3
WISH_KEEP_REDEEMED_PER_CHILD: Final = 20
NOTIF_TYPE_WISH_REQUESTED: Final = "wish_requested"
NOTIF_TYPE_WISH_PLEDGED: Final = "wish_pledged"
SERVICE_ADD_WISH: Final = "add_wish"
SERVICE_WITHDRAW_WISH: Final = "withdraw_wish"
SERVICE_MOVE_POINTS_TO_WISH: Final = "move_points_to_wish"
SERVICE_TAKE_POINTS_FROM_WISH: Final = "take_points_from_wish"
SERVICE_REQUEST_WISH_REDEEM: Final = "request_wish_redeem"
SERVICE_APPROVE_WISH: Final = "approve_wish"
SERVICE_DECLINE_WISH: Final = "decline_wish"
SERVICE_PLEDGE_TO_WISH: Final = "pledge_to_wish"
SERVICE_REMOVE_WISH_PLEDGE: Final = "remove_wish_pledge"
SERVICE_REMOVE_WISH: Final = "remove_wish"
