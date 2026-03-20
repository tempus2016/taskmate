"""Constants for Choremander integration."""
from typing import Final

DOMAIN: Final = "choremander"

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

# Chore keys
CONF_CHORE_NAME: Final = "name"
CONF_CHORE_DESCRIPTION: Final = "description"
CONF_CHORE_POINTS: Final = "points"
CONF_CHORE_DUE_DAYS: Final = "due_days"
CONF_CHORE_ASSIGNED_TO: Final = "assigned_to"
CONF_CHORE_ID: Final = "id"
CONF_CHORE_REQUIRES_APPROVAL: Final = "requires_approval"

# Reward keys
CONF_REWARD_NAME: Final = "name"
CONF_REWARD_DESCRIPTION: Final = "description"
CONF_REWARD_COST: Final = "cost"
CONF_REWARD_ICON: Final = "icon"
CONF_REWARD_ID: Final = "id"

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
SERVICE_ADD_POINTS: Final = "add_points"
SERVICE_REMOVE_POINTS: Final = "remove_points"
SERVICE_RESET_DAILY: Final = "reset_daily"
SERVICE_SET_CHORE_ORDER: Final = "set_chore_order"
SERVICE_PREVIEW_SOUND: Final = "preview_sound"

# Events
EVENT_PREVIEW_SOUND: Final = "choremander_preview_sound"

# Attributes
ATTR_CHILD_ID: Final = "child_id"
ATTR_CHORE_ID: Final = "chore_id"
ATTR_REWARD_ID: Final = "reward_id"
ATTR_POINTS: Final = "points"
ATTR_REASON: Final = "reason"
ATTR_CHORE_ORDER: Final = "chore_order"
ATTR_SOUND: Final = "sound"

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
