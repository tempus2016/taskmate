"""Constants for TaskMate integration."""
from typing import Final

DOMAIN: Final = "taskmate"

# Configuration keys
CONF_CHILDREN: Final = "children"
CONF_CHORES: Final = "chores"
CONF_REWARDS: Final = "rewards"
CONF_POINTS_NAME: Final = "points_name"
CONF_POINTS_ICON: Final = "points_icon"

# Child keys
CONF_CHILD_NAME: Final = "name"
CONF_CHILD_AVATAR: Final = "avatar"
CONF_CHILD_POINTS: Final = "points"
CONF_CHILD_ID: Final = "id"
CONF_CHILD_AVAILABILITY_ENTITY: Final = "availability_entity"

# Chore keys
CONF_CHORE_NAME: Final = "name"
CONF_CHORE_DESCRIPTION: Final = "description"
CONF_CHORE_POINTS: Final = "points"
CONF_CHORE_DUE_DAYS: Final = "due_days"
CONF_CHORE_ASSIGNED_TO: Final = "assigned_to"
CONF_CHORE_ID: Final = "id"
CONF_CHORE_REQUIRES_APPROVAL: Final = "requires_approval"
CONF_CLAIM_ALLOWANCE_MINUTES: Final = "claim_allowance_minutes"
DEFAULT_CLAIM_ALLOWANCE_MINUTES: Final = 0
CONF_CHORE_ASSIGNMENT_MODE: Final = "assignment_mode"
CONF_CHORE_ASSIGNMENT_ROTATION_ANCHOR: Final = "assignment_rotation_anchor"
CONF_CHORE_PUBLISH_CALENDARS: Final = "publish_calendar_entities"
CONF_CHORE_REQUIRE_AVAILABILITY: Final = "require_availability"
CONF_CHORE_MANUAL_START_CHILD: Final = "manual_start_child_id"

# Task groups
CONF_TASK_GROUPS: Final = "task_groups"
CONF_TASK_GROUP_ID: Final = "group_id"
CONF_TASK_GROUP_NAME: Final = "name"
CONF_TASK_GROUP_POLICY: Final = "policy"
CONF_TASK_GROUP_CHORE_IDS: Final = "chore_ids"
TASK_GROUP_POLICIES: Final = ["sticky", "spread"]
DEFAULT_TASK_GROUP_POLICY: Final = "sticky"

# Calendar projection: how many days ahead each chore's assignment is pushed
# into the configured HA calendars. 14 days balances planning visibility with
# calendar noise; raise via the Settings flow for longer planning horizons.
CONF_CALENDAR_PROJECTION_DAYS: Final = "calendar_projection_days"
DEFAULT_CALENDAR_PROJECTION_DAYS: Final = 14
MIN_CALENDAR_PROJECTION_DAYS: Final = 1
MAX_CALENDAR_PROJECTION_DAYS: Final = 90

# Assignment modes
# "everyone"    = visible to every child in assigned_to (or all children if empty) -- existing behavior
# "alternating" = round-robin through assigned_to (or all children), one child per calendar day
# "random"      = deterministic per-day random pick from the same pool (each chore picks independently)
# "balanced"    = split today's balanced-mode chores evenly across the pool so no one child gets swamped
ASSIGNMENT_MODES: Final = ["everyone", "alternating", "random", "balanced", "unassigned"]
DEFAULT_ASSIGNMENT_MODE: Final = "everyone"

# Reward keys
CONF_REWARD_NAME: Final = "name"
CONF_REWARD_DESCRIPTION: Final = "description"
CONF_REWARD_COST: Final = "cost"
CONF_REWARD_ICON: Final = "icon"
CONF_REWARD_ID: Final = "id"
CONF_REWARD_QUANTITY: Final = "quantity"
CONF_REWARD_EXPIRES_AT: Final = "expires_at"

# Default values
DEFAULT_POINTS_NAME: Final = "Stars"
DEFAULT_POINTS_ICON: Final = "mdi:star"

# Days of week
DAYS_OF_WEEK: Final = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

# Recurrence options for chores (Mode B)
RECURRENCE_OPTIONS: Final = [
    "every_2_days",
    "weekly",
    "every_2_weeks",
    "monthly",
    "every_3_months",
    "every_6_months",
]

RECURRENCE_LABELS: Final = {
    "every_2_days": "Every 2 days",
    "weekly": "Weekly",
    "every_2_weeks": "Every 2 weeks",
    "monthly": "Monthly",
    "every_3_months": "Every 3 months",
    "every_6_months": "Every 6 months",
}

# Schedule modes
SCHEDULE_MODES: Final = ["specific_days", "recurring", "one_shot"]

# First occurrence modes
FIRST_OCCURRENCE_MODES: Final = ["available_immediately", "wait_for_first_occurrence"]

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

# Avatar options
AVATAR_OPTIONS: Final = [
    # Basic faces
    "mdi:account-circle",
    "mdi:face-man",
    "mdi:face-woman",
    "mdi:face-man-outline",
    "mdi:face-woman-outline",
    # Fun character avatars
    "mdi:robot-happy",
    "mdi:robot-excited",
    "mdi:alien",
    "mdi:ninja",
    "mdi:pirate",
    # Animals kids love
    "mdi:cat",
    "mdi:dog",
    "mdi:unicorn",
    "mdi:dragon",
    "mdi:owl",
    "mdi:penguin",
    "mdi:panda",
    "mdi:rabbit",
    "mdi:koala",
    "mdi:fox",
    "mdi:dolphin",
    "mdi:jellyfish",
    "mdi:octopus",
    "mdi:butterfly",
    # Splatoon Inkling-inspired (colorful, action-themed)
    "mdi:palette",
    "mdi:spray",
    "mdi:water-outline",
    "mdi:shimmer",
    "mdi:flare",
    "mdi:star-face",
    "mdi:emoticon-cool",
    "mdi:emoticon-excited",
    "mdi:emoticon-kiss",
    "mdi:emoticon-wink",
    "mdi:emoticon-happy",
    "mdi:emoticon-poop",
    "mdi:face-woman-shimmer",
    "mdi:face-man-shimmer",
    "mdi:account-star",
    "mdi:account-heart",
    # Gaming and action themed
    "mdi:gamepad-variant",
    "mdi:controller",
    "mdi:trophy",
    "mdi:crown",
    "mdi:lightning-bolt",
    "mdi:fire",
    "mdi:rocket",
    "mdi:sword",
    "mdi:shield",
    # Space and fantasy
    "mdi:alien-outline",
    "mdi:ufo",
    "mdi:space-invaders",
    "mdi:ghost",
    "mdi:skull-crossbones",
    "mdi:wizard-hat",
    "mdi:magic-staff",
    # Nature and colorful
    "mdi:flower-tulip",
    "mdi:flower-poppy",
    "mdi:clover",
    "mdi:mushroom",
    "mdi:star-shooting",
    "mdi:star-four-points",
    "mdi:heart",
    "mdi:heart-multiple",
    "mdi:diamond-stone",
    "mdi:puzzle-heart",
]

# Reward icon options
REWARD_ICON_OPTIONS: Final = [
    "mdi:gift",
    "mdi:ice-cream",
    "mdi:pizza",
    "mdi:movie",
    "mdi:gamepad-variant",
    "mdi:tablet",
    "mdi:television",
    "mdi:bike",
    "mdi:currency-usd",
    "mdi:shopping",
    "mdi:party-popper",
    "mdi:swim",
    "mdi:sleep",
    "mdi:candy",
]

# Platforms
PLATFORMS: Final = ["sensor", "button", "binary_sensor"]

# Services
SERVICE_COMPLETE_CHORE: Final = "complete_chore"
SERVICE_APPROVE_CHORE: Final = "approve_chore"
SERVICE_REJECT_CHORE: Final = "reject_chore"
SERVICE_CLAIM_REWARD: Final = "claim_reward"
SERVICE_APPROVE_REWARD: Final = "approve_reward"
SERVICE_REJECT_REWARD: Final = "reject_reward"
SERVICE_ADD_POINTS: Final = "add_points"
SERVICE_REMOVE_POINTS: Final = "remove_points"
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

# Events
EVENT_PREVIEW_SOUND: Final = "taskmate_preview_sound"

# Attributes
ATTR_CHILD_ID: Final = "child_id"
ATTR_CHORE_ID: Final = "chore_id"
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
ATTR_BONUS_SUBTASK_ID: Final = "bonus_subtask_id"

# Badge attributes
ATTR_BADGE_ID: Final = "badge_id"
ATTR_BADGE_NAME: Final = "name"
ATTR_BADGE_DESCRIPTION: Final = "description"
ATTR_BADGE_ICON: Final = "icon"
ATTR_BADGE_TIER: Final = "tier"
ATTR_BADGE_POINT_BONUS: Final = "point_bonus"
ATTR_BADGE_CRITERIA: Final = "criteria"
ATTR_BADGE_ASSIGNED_TO: Final = "assigned_to"
ATTR_BADGE_NOTIFY_ON_EARN: Final = "notify_on_earn"
ATTR_BADGE_ENABLED: Final = "enabled"
ATTR_AWARDED_BADGE_ID: Final = "awarded_badge_id"

# States
STATE_PENDING: Final = "pending"
STATE_AWAITING_APPROVAL: Final = "awaiting_approval"
STATE_COMPLETED: Final = "completed"
STATE_CLAIMED: Final = "claimed"

# Completion sound options
# Most sounds are synthesized via Web Audio API
# Fart sounds are CC0 audio files from BigSoundBank.com and GfxSounds.com
COMPLETION_SOUND_OPTIONS: Final = [
    "none",        # No sound
    "coin",        # Coin collect sound
    "levelup",     # Level up / success sound
    "fanfare",     # Celebratory fanfare
    "chime",       # Simple chime
    "powerup",     # Power up sound
    "undo",        # Sad/descending "womp womp" for undo actions
    "fart1",       # Flatulence 1 (short)
    "fart2",       # Flatulence 2 (short)
    "fart3",       # Flatulence 3 (short)
    "fart4",       # Pony flatulence 2 (~3 sec)
    "fart5",       # Flatulence 4 - discreet (short)
    "fart6",       # Prout'cochons 1 - pig game sound (short)
    "fart7",       # Prout'cochons 2 - pig game sound (short)
    "fart8",       # Prout'cochons 3 - pig game sound (short)
    "fart9",       # Pony flatulence 1 (short)
    "fart10",      # Baby fart (short)
    "fart_random", # Random fart - picks a random fart sound each time!
]

# Default completion sound
DEFAULT_COMPLETION_SOUND: Final = "coin"

# Chore keys (sound-related)
CONF_CHORE_COMPLETION_SOUND: Final = "completion_sound"
