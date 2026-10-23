"""Suggestions for the setup wizard (#980).

Chores suggested by age group and a handful of starter rewards. Only ids,
points, schedules and icons live here: every name is a translation key in the
panel's locale files (``wizard.chore.<id>`` / ``wizard.reward.<id>``), so a
chore the wizard creates takes the family's language at creation time.
``tests/test_setup_wizard.py`` checks every id has a name in every locale.

Rewards have fixed costs, like every other reward.
"""

from __future__ import annotations

from typing import Any

from .const import AGE_GROUPS
from .templates import BUILT_IN_TEMPLATES

_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]

# Each age group: its youngest and oldest age (None = no upper limit), plus the
# colour and icon the wizard draws its heading with.
AGE_GROUP_INFO: dict[str, dict[str, Any]] = {
    "3_5": {"min_age": 3, "max_age": 5, "color": "#1abc9c", "icon": "mdi:toy-brick-outline"},
    "6_8": {"min_age": 6, "max_age": 8, "color": "#3498db", "icon": "mdi:bed-outline"},
    "9_12": {"min_age": 9, "max_age": 12, "color": "#ff6b9d", "icon": "mdi:dishwasher"},
    "13_plus": {"min_age": 13, "max_age": None, "color": "#9b59b6", "icon": "mdi:pot-steam-outline"},
}

# How often a suggestion comes round, as chore schedule fields, and roughly how
# many times a week that is (the wizard's "per week" estimate).
FREQUENCIES: dict[str, dict[str, Any]] = {
    "daily": {"schedule_mode": "specific_days", "per_week": 7},
    "weekdays": {"schedule_mode": "specific_days", "per_week": 5},
    "days": {"schedule_mode": "specific_days", "per_week": None},  # per_week = number of days
    "weekly": {"schedule_mode": "recurring", "recurrence": "weekly", "per_week": 1},
    "every_2_weeks": {"schedule_mode": "recurring", "recurrence": "every_2_weeks", "per_week": 0.5},
    "monthly": {"schedule_mode": "recurring", "recurrence": "monthly", "per_week": 0.25},
}


def _s(sid: str, age_group: str, points: int, freq: str, time: str, icon: str, days: list[str] | None = None) -> dict:
    return {
        "id": sid,
        "age_group": age_group,
        "points": points,
        "frequency": freq,
        "days": list(days or []),
        "time_category": time,
        "icon": icon,
    }


# About eight per age group; the wizard ticks the first five for each group a
# child is in. Points rise with age and with the size of the job.
SUGGESTED_CHORES: list[dict] = [
    # 3–5: one-step jobs
    _s("toys_away", "3_5", 1, "daily", "evening", "mdi:toy-brick-outline"),
    _s("clothes_basket", "3_5", 1, "daily", "evening", "mdi:basket-outline"),
    _s("brush_teeth_help", "3_5", 1, "daily", "morning", "mdi:toothbrush"),
    _s("shoes_coat", "3_5", 1, "daily", "afternoon", "mdi:shoe-sneaker"),
    _s("help_feed_pet", "3_5", 1, "daily", "morning", "mdi:paw"),
    _s("match_socks", "3_5", 1, "days", "anytime", "mdi:shoe-print", ["saturday"]),
    _s("napkins", "3_5", 1, "daily", "evening", "mdi:silverware-fork-knife"),
    _s("water_plant", "3_5", 1, "days", "anytime", "mdi:sprout-outline", ["wednesday", "saturday"]),
    # 6–8: routines they tick off themselves
    _s("make_bed", "6_8", 2, "daily", "morning", "mdi:bed-outline"),
    _s("get_dressed", "6_8", 1, "daily", "morning", "mdi:tshirt-crew-outline"),
    _s("pack_school_bag", "6_8", 2, "weekdays", "morning", "mdi:bag-personal-outline"),
    _s("set_clear_table", "6_8", 2, "daily", "evening", "mdi:silverware-variant"),
    _s("tidy_bedroom", "6_8", 3, "days", "anytime", "mdi:broom", ["saturday"]),
    _s("feed_pet", "6_8", 2, "daily", "morning", "mdi:paw"),
    _s("put_away_laundry", "6_8", 2, "days", "anytime", "mdi:tshirt-crew", ["tuesday", "friday"]),
    _s("read_15", "6_8", 2, "daily", "anytime", "mdi:book-open-variant"),
    # 9–12: real household jobs
    _s("dishwasher", "9_12", 3, "daily", "evening", "mdi:dishwasher"),
    _s("bins_out", "9_12", 3, "days", "anytime", "mdi:delete-outline", ["tuesday"]),
    _s("hoover_room", "9_12", 4, "days", "anytime", "mdi:vacuum-outline", ["saturday"]),
    _s("walk_dog", "9_12", 3, "daily", "afternoon", "mdi:dog-side"),
    _s("help_cook", "9_12", 4, "days", "evening", "mdi:pot-steam-outline", ["wednesday", "sunday"]),
    _s("clean_sink", "9_12", 3, "days", "anytime", "mdi:faucet", ["sunday"]),
    _s("homework_no_reminders", "9_12", 3, "weekdays", "afternoon", "mdi:pencil-outline"),
    _s("change_sheets", "9_12", 4, "every_2_weeks", "anytime", "mdi:bed-king-outline", ["sunday"]),
    # 13+: life skills
    _s("cook_meal", "13_plus", 8, "days", "evening", "mdi:chef-hat", ["friday"]),
    _s("own_laundry", "13_plus", 5, "weekly", "anytime", "mdi:washing-machine"),
    _s("mow_lawn", "13_plus", 8, "every_2_weeks", "anytime", "mdi:mower", ["saturday"]),
    _s("clean_bathroom", "13_plus", 6, "days", "anytime", "mdi:shower-head", ["sunday"]),
    _s("wash_car", "13_plus", 6, "monthly", "anytime", "mdi:car-wash"),
    _s("babysit", "13_plus", 8, "weekly", "anytime", "mdi:baby-face-outline"),
    _s("food_shop", "13_plus", 5, "days", "anytime", "mdi:cart-outline", ["saturday"]),
    _s("recycling", "13_plus", 3, "days", "anytime", "mdi:recycle", ["tuesday"]),
]

# ── Library (the 📚 dialog) ──────────────────────────────────────────────────
# About 200 chores in 12 categories and 45 rewards, browsable from the Chores
# and Rewards tabs and from the wizard. The wizard's suggestions above are the
# library's "top picks"; everything here is named by translation key like they
# are (``wizard.chore.<id>`` / ``wizard.reward.<id>``, ``wizard.cat.<id>``).
# A chore suits a child whose age is between ``min_age`` and ``max_age``
# (None = no upper limit).
CHORE_CATEGORIES: tuple[str, ...] = (
    "morning",
    "school",
    "kitchen",
    "tidy",
    "laundry",
    "outdoor",
    "pets",
    "responsibility",
    "health",
    "family",
    "evening",
    "learning",
)

# Where each wizard suggestion sits in the library, and the oldest age it
# still suits when that is capped (the rest suit their group and older).
_TOP_PICK_CATEGORY: dict[str, str] = {
    "toys_away": "tidy",
    "clothes_basket": "laundry",
    "brush_teeth_help": "morning",
    "shoes_coat": "tidy",
    "help_feed_pet": "pets",
    "match_socks": "laundry",
    "napkins": "kitchen",
    "water_plant": "outdoor",
    "make_bed": "morning",
    "get_dressed": "morning",
    "pack_school_bag": "school",
    "set_clear_table": "kitchen",
    "tidy_bedroom": "tidy",
    "feed_pet": "pets",
    "put_away_laundry": "laundry",
    "read_15": "school",
    "dishwasher": "kitchen",
    "bins_out": "outdoor",
    "hoover_room": "tidy",
    "walk_dog": "pets",
    "help_cook": "kitchen",
    "clean_sink": "tidy",
    "homework_no_reminders": "school",
    "change_sheets": "laundry",
    "cook_meal": "kitchen",
    "own_laundry": "laundry",
    "mow_lawn": "outdoor",
    "clean_bathroom": "tidy",
    "wash_car": "outdoor",
    "babysit": "responsibility",
    "food_shop": "responsibility",
    "recycling": "outdoor",
}
_TOP_PICK_MAX_AGE: dict[str, int] = {"brush_teeth_help": 6, "help_feed_pet": 8, "napkins": 10, "match_socks": 10}


def _c(
    sid: str,
    category: str,
    min_age: int,
    max_age: int | None,
    points: int,
    freq: str,
    time: str,
    icon: str,
    days: list[str] | None = None,
) -> dict:
    return {
        "id": sid,
        "category": category,
        "min_age": min_age,
        "max_age": max_age,
        "points": points,
        "frequency": freq,
        "days": list(days or []),
        "time_category": time,
        "icon": icon,
    }


_WE = ["saturday", "sunday"]
_TWICE = ["wednesday", "saturday"]

# The rest of the library: everything that isn't a wizard suggestion.
LIBRARY_EXTRA_CHORES: list[dict] = [
    _c("brush_teeth_am", "morning", 5, None, 1, "daily", "morning", "mdi:toothbrush-paste"),
    _c("wash_face", "morning", 4, None, 1, "daily", "morning", "mdi:face-man-shimmer"),
    _c("brush_hair", "morning", 4, None, 1, "daily", "morning", "mdi:hair-dryer"),
    _c("pyjamas_away", "morning", 3, 10, 1, "daily", "morning", "mdi:tshirt-crew-outline"),
    _c("clear_breakfast", "morning", 4, None, 1, "daily", "morning", "mdi:bowl-mix-outline"),
    _c("up_with_alarm", "morning", 9, None, 2, "weekdays", "morning", "mdi:alarm"),
    _c("make_breakfast", "morning", 9, None, 2, "days", "morning", "mdi:bread-slice-outline", _WE),
    _c("pack_lunch", "morning", 10, None, 3, "weekdays", "morning", "mdi:food-takeout-box-outline"),
    _c("sun_cream", "morning", 4, 12, 1, "daily", "morning", "mdi:weather-sunny"),
    _c("ready_to_go", "morning", 4, 10, 1, "weekdays", "morning", "mdi:coat-rack"),
    _c("open_curtains", "morning", 3, 10, 1, "daily", "morning", "mdi:curtains"),
    _c("eat_breakfast_table", "morning", 3, 8, 1, "daily", "morning", "mdi:silverware-fork-knife"),
    _c("school_letters", "school", 5, 11, 1, "weekdays", "afternoon", "mdi:email-outline"),
    _c("pack_pe_kit", "school", 6, None, 1, "weekly", "evening", "mdi:bag-personal-outline"),
    _c("spellings", "school", 6, 11, 2, "weekdays", "afternoon", "mdi:alphabetical-variant"),
    _c("times_tables", "school", 7, 11, 2, "weekdays", "afternoon", "mdi:multiplication"),
    _c("check_school_app", "school", 11, None, 1, "weekdays", "afternoon", "mdi:cellphone-check"),
    _c("plan_homework_week", "school", 12, None, 2, "days", "evening", "mdi:calendar-check-outline", ["sunday"]),
    _c("revision_session", "school", 13, None, 4, "weekdays", "afternoon", "mdi:book-education-outline"),
    _c("tidy_pencil_case", "school", 6, 12, 1, "weekly", "anytime", "mdi:pencil-box-outline"),
    _c("wash_water_bottle", "school", 7, None, 1, "weekdays", "afternoon", "mdi:bottle-soda-classic-outline"),
    _c("empty_lunchbox", "school", 5, None, 1, "weekdays", "afternoon", "mdi:food-apple-outline"),
    _c("instrument_practice", "school", 7, None, 3, "weekdays", "afternoon", "mdi:guitar-acoustic"),
    _c("read_aloud", "school", 5, 9, 2, "weekdays", "afternoon", "mdi:book-open-page-variant-outline"),
    _c("set_table", "kitchen", 4, None, 1, "daily", "evening", "mdi:silverware-variant"),
    _c("clear_table", "kitchen", 4, None, 1, "daily", "evening", "mdi:table-furniture"),
    _c("empty_dishwasher", "kitchen", 8, None, 2, "daily", "anytime", "mdi:dishwasher"),
    _c("make_lunch_weekend", "kitchen", 10, None, 2, "days", "afternoon", "mdi:food-variant", _WE),
    _c("wash_veg", "kitchen", 5, None, 1, "days", "evening", "mdi:carrot", _TWICE),
    _c("wipe_table", "kitchen", 5, None, 1, "daily", "evening", "mdi:spray-bottle"),
    _c("wash_up", "kitchen", 10, None, 3, "daily", "evening", "mdi:dishwasher-alert"),
    _c("dry_up", "kitchen", 7, None, 2, "daily", "evening", "mdi:silverware-clean"),
    _c("bake_together", "kitchen", 6, None, 3, "weekly", "anytime", "mdi:cookie-outline"),
    _c("unpack_shopping", "kitchen", 6, None, 2, "weekly", "anytime", "mdi:shopping-outline"),
    _c("clear_fridge", "kitchen", 12, None, 3, "weekly", "anytime", "mdi:fridge-outline"),
    _c("toast_for_all", "kitchen", 9, None, 2, "days", "morning", "mdi:toaster", _WE),
    _c("fill_water_jug", "kitchen", 4, 9, 1, "daily", "evening", "mdi:cup-water"),
    _c("food_prep", "kitchen", 11, None, 3, "days", "evening", "mdi:knife", _TWICE),
    _c("plan_dinner", "kitchen", 11, None, 2, "weekly", "anytime", "mdi:clipboard-text-outline"),
    _c("wipe_counters", "kitchen", 8, None, 2, "daily", "evening", "mdi:countertop-outline"),
    _c("mop_floor", "tidy", 12, None, 4, "weekly", "anytime", "mdi:bucket-outline"),
    _c("dust_room", "tidy", 8, None, 2, "weekly", "anytime", "mdi:feather"),
    _c("clean_mirrors", "tidy", 9, None, 2, "weekly", "anytime", "mdi:mirror"),
    _c("empty_bedroom_bin", "tidy", 6, None, 1, "weekly", "anytime", "mdi:delete-empty-outline"),
    _c("tidy_living_room", "tidy", 7, None, 2, "daily", "evening", "mdi:sofa-outline"),
    _c("line_up_shoes", "tidy", 3, 9, 1, "daily", "anytime", "mdi:shoe-sneaker"),
    _c("sort_drawer", "tidy", 8, None, 3, "monthly", "anytime", "mdi:dresser-outline"),
    _c("toilet_roll", "tidy", 6, None, 1, "weekly", "anytime", "mdi:paper-roll-outline"),
    _c("clean_windows", "tidy", 12, None, 4, "monthly", "anytime", "mdi:window-closed-variant"),
    _c("clean_toilet", "tidy", 12, None, 4, "weekly", "anytime", "mdi:toilet"),
    _c("wipe_handles", "tidy", 9, None, 2, "weekly", "anytime", "mdi:light-switch"),
    _c("rinse_bath", "tidy", 8, None, 1, "daily", "night", "mdi:bathtub-outline"),
    _c("games_in_box", "tidy", 3, 10, 1, "daily", "anytime", "mdi:puzzle-outline"),
    _c("tidy_desk", "tidy", 8, None, 2, "weekly", "anytime", "mdi:desk"),
    _c("clear_stairs", "tidy", 5, None, 1, "daily", "evening", "mdi:stairs"),
    _c("tidy_car", "tidy", 10, None, 2, "weekly", "anytime", "mdi:car-outline"),
    _c("declutter", "tidy", 8, None, 4, "monthly", "anytime", "mdi:package-variant"),
    _c("hoover_stairs", "tidy", 11, None, 3, "weekly", "anytime", "mdi:vacuum"),
    _c("make_bed_tidy", "tidy", 3, 5, 1, "daily", "morning", "mdi:bed-outline"),
    _c("sort_colours", "laundry", 7, None, 1, "weekly", "anytime", "mdi:palette-outline"),
    _c("hang_washing", "laundry", 9, None, 2, "days", "anytime", "mdi:hanger", _TWICE),
    _c("fold_towels", "laundry", 6, None, 1, "weekly", "anytime", "mdi:rug"),
    _c("load_washer", "laundry", 10, None, 2, "weekly", "anytime", "mdi:washing-machine"),
    _c("iron_shirts", "laundry", 14, None, 3, "weekly", "anytime", "mdi:iron-outline"),
    _c("clean_trainers", "laundry", 10, None, 2, "monthly", "anytime", "mdi:shoe-print"),
    _c("pair_gloves", "laundry", 4, 10, 1, "weekly", "anytime", "mdi:hat-fedora"),
    _c("bring_washing_in", "laundry", 7, None, 1, "days", "afternoon", "mdi:basket-fill", _TWICE),
    _c("fold_clothes", "laundry", 8, None, 2, "weekly", "anytime", "mdi:tshirt-v-outline"),
    _c("sort_wardrobe", "laundry", 11, None, 3, "monthly", "anytime", "mdi:wardrobe-outline"),
    _c("rake_leaves", "outdoor", 8, None, 4, "weekly", "anytime", "mdi:leaf"),
    _c("weed_bed", "outdoor", 8, None, 3, "weekly", "anytime", "mdi:flower-outline"),
    _c("clear_snow", "outdoor", 11, None, 4, "daily", "morning", "mdi:snowflake"),
    _c("sweep_patio", "outdoor", 9, None, 2, "weekly", "anytime", "mdi:broom"),
    _c("bring_post_in", "outdoor", 5, None, 1, "daily", "afternoon", "mdi:mailbox-outline"),
    _c("bike_away", "outdoor", 6, None, 1, "daily", "evening", "mdi:bike"),
    _c("repot_plant", "outdoor", 9, None, 2, "monthly", "anytime", "mdi:pot-mix-outline"),
    _c("bird_feeder", "outdoor", 5, None, 1, "weekly", "anytime", "mdi:bird"),
    _c("diy_help", "outdoor", 11, None, 4, "monthly", "anytime", "mdi:hammer-wrench"),
    _c("bins_back_in", "outdoor", 8, None, 1, "weekly", "afternoon", "mdi:trash-can-outline"),
    _c("pick_veg", "outdoor", 4, None, 1, "weekly", "anytime", "mdi:fruit-cherries"),
    _c("clean_garden_furniture", "outdoor", 10, None, 3, "monthly", "anytime", "mdi:table-chair"),
    _c("water_garden", "outdoor", 6, None, 2, "days", "evening", "mdi:watering-can-outline", _TWICE),
    _c("sweep_path", "outdoor", 7, None, 2, "weekly", "anytime", "mdi:home-outline"),
    _c("pet_water", "pets", 3, None, 1, "daily", "anytime", "mdi:water-outline"),
    _c("litter_tray", "pets", 10, None, 3, "daily", "anytime", "mdi:cat"),
    _c("clean_cage", "pets", 9, None, 4, "weekly", "anytime", "mdi:rodent"),
    _c("feed_fish", "pets", 4, None, 1, "daily", "morning", "mdi:fish"),
    _c("brush_dog", "pets", 7, None, 2, "weekly", "anytime", "mdi:dog"),
    _c("clean_hutch", "pets", 10, None, 4, "weekly", "anytime", "mdi:rabbit"),
    _c("play_with_pet", "pets", 4, None, 1, "daily", "anytime", "mdi:tennis-ball"),
    _c("dog_poo", "pets", 11, None, 2, "weekly", "anytime", "mdi:shovel"),
    _c("tank_water", "pets", 12, None, 3, "every_2_weeks", "anytime", "mdi:fishbowl-outline"),
    _c("pet_food_out", "pets", 7, None, 2, "daily", "evening", "mdi:food-drumstick-outline"),
    _c("charge_devices", "responsibility", 9, None, 1, "daily", "night", "mdi:battery-charging-outline"),
    _c("weekly_plan", "responsibility", 12, None, 2, "days", "evening", "mdi:calendar-week", ["sunday"]),
    _c("money_jar", "responsibility", 6, 12, 1, "weekly", "anytime", "mdi:piggy-bank-outline"),
    _c("call_grandparent", "responsibility", 6, None, 2, "weekly", "anytime", "mdi:phone-outline"),
    _c("thank_you_card", "responsibility", 6, None, 2, "monthly", "anytime", "mdi:card-text-outline"),
    _c("help_sibling_ready", "responsibility", 9, None, 2, "weekdays", "morning", "mdi:human-male-child"),
    _c("on_time", "responsibility", 6, None, 2, "weekdays", "morning", "mdi:clock-check-outline"),
    _c("phone_in_basket", "responsibility", 11, None, 2, "daily", "night", "mdi:cellphone-off"),
    _c("budget_money", "responsibility", 11, None, 2, "monthly", "anytime", "mdi:cash-multiple"),
    _c("shop_alone", "responsibility", 11, None, 3, "monthly", "anytime", "mdi:store-outline"),
    _c("club_bag", "responsibility", 8, None, 1, "weekly", "evening", "mdi:bag-checked"),
    _c("visitor_drink", "responsibility", 8, None, 1, "weekly", "anytime", "mdi:coffee-outline"),
    _c("remember_key", "responsibility", 12, None, 1, "weekdays", "morning", "mdi:key-outline"),
    _c("check_bus", "responsibility", 12, None, 1, "weekdays", "morning", "mdi:bus"),
    _c("lay_out_clothes", "responsibility", 7, None, 1, "weekdays", "evening", "mdi:hanger"),
    _c("drink_water", "health", 5, None, 1, "daily", "anytime", "mdi:cup-water"),
    _c("outside_30", "health", 4, None, 2, "daily", "anytime", "mdi:pine-tree"),
    _c("floss", "health", 9, None, 1, "daily", "night", "mdi:tooth-outline"),
    _c("eat_fruit", "health", 3, None, 1, "daily", "anytime", "mdi:food-apple"),
    _c("try_veg", "health", 3, None, 2, "weekly", "evening", "mdi:food-variant"),
    _c("calm_breathing", "health", 7, None, 1, "daily", "night", "mdi:meditation"),
    _c("ride_bike", "health", 6, None, 2, "days", "anytime", "mdi:bike-fast", _TWICE),
    _c("sports_practice", "health", 7, None, 3, "days", "afternoon", "mdi:soccer", _TWICE),
    _c("walk_to_school", "health", 9, None, 2, "weekdays", "morning", "mdi:walk"),
    _c("screen_free_hour", "health", 7, None, 2, "daily", "anytime", "mdi:television-off"),
    _c("skincare", "health", 11, None, 1, "daily", "night", "mdi:lotion-outline"),
    _c("stretch", "health", 8, None, 1, "daily", "anytime", "mdi:human-handsup"),
    _c("swimming", "health", 6, None, 3, "weekly", "anytime", "mdi:swim"),
    _c("bed_on_time", "health", 4, None, 2, "daily", "night", "mdi:sleep"),
    _c("take_medicine", "health", 4, None, 1, "daily", "morning", "mdi:pill"),
    _c("wash_hands_dinner", "health", 3, None, 1, "daily", "evening", "mdi:hand-wash-outline"),
    _c("help_unasked", "family", 5, None, 2, "daily", "anytime", "mdi:hand-heart-outline"),
    _c("game_night", "family", 7, None, 2, "weekly", "evening", "mdi:dice-multiple-outline"),
    _c("tell_about_day", "family", 4, None, 1, "daily", "evening", "mdi:chat-outline"),
    _c("kind_neighbour", "family", 8, None, 3, "monthly", "anytime", "mdi:home-heart"),
    _c("kind_to_sibling", "family", 4, None, 1, "daily", "anytime", "mdi:emoticon-happy-outline"),
    _c("birthday_card", "family", 5, None, 2, "monthly", "anytime", "mdi:cake-variant-outline"),
    _c("plan_treat", "family", 9, None, 2, "monthly", "anytime", "mdi:party-popper"),
    _c("visit_grandparents", "family", 8, None, 3, "monthly", "anytime", "mdi:account-heart-outline"),
    _c("make_gift", "family", 4, None, 2, "weekly", "anytime", "mdi:gift-outline"),
    _c("sort_argument", "family", 8, None, 3, "weekly", "anytime", "mdi:handshake-outline"),
    _c("hug_goodnight", "family", 3, 8, 1, "daily", "night", "mdi:heart-outline"),
    _c("brush_teeth_pm", "evening", 5, None, 1, "daily", "night", "mdi:toothbrush"),
    _c("bath_shower", "evening", 4, None, 1, "daily", "night", "mdi:shower-head"),
    _c("bedtime_reading", "evening", 4, None, 1, "daily", "night", "mdi:book-open-variant"),
    _c("tidy_before_bed", "evening", 3, None, 1, "daily", "night", "mdi:toy-brick-outline"),
    _c("devices_away", "evening", 10, None, 2, "daily", "night", "mdi:tablet"),
    _c("pyjamas_on", "evening", 3, 8, 1, "daily", "night", "mdi:weather-night"),
    _c("lights_out", "evening", 8, None, 2, "daily", "night", "mdi:lightbulb-off-outline"),
    _c("clear_cup", "evening", 5, None, 1, "daily", "evening", "mdi:cup-outline"),
    _c("check_tomorrow", "evening", 10, None, 1, "daily", "night", "mdi:calendar-today"),
    _c("tablet_kitchen", "evening", 7, None, 1, "daily", "night", "mdi:power-plug-outline"),
    _c("school_bag_by_door", "evening", 6, None, 1, "weekdays", "night", "mdi:door"),
    _c("practise_piano", "learning", 6, None, 3, "weekdays", "afternoon", "mdi:piano"),
    _c("language_words", "learning", 8, None, 2, "daily", "anytime", "mdi:translate"),
    _c("brain_game", "learning", 5, None, 1, "daily", "anytime", "mdi:head-lightbulb-outline"),
    _c("diary", "learning", 8, None, 1, "daily", "night", "mdi:notebook-outline"),
    _c("science_experiment", "learning", 7, None, 3, "monthly", "anytime", "mdi:flask-outline"),
    _c("draw_paint", "learning", 4, None, 1, "days", "anytime", "mdi:palette", _TWICE),
    _c("news_together", "learning", 11, None, 2, "weekly", "anytime", "mdi:newspaper-variant-outline"),
    _c("typing_practice", "learning", 9, None, 1, "days", "anytime", "mdi:keyboard-outline", _TWICE),
    _c("chess_game", "learning", 7, None, 1, "weekly", "anytime", "mdi:chess-knight"),
    _c("sew_button", "learning", 10, None, 3, "monthly", "anytime", "mdi:needle"),
    _c("coding_practice", "learning", 10, None, 3, "weekly", "anytime", "mdi:code-tags"),
    _c("learn_song", "learning", 6, None, 2, "weekly", "anytime", "mdi:microphone-variant"),
    _c("photo_project", "learning", 10, None, 2, "weekly", "anytime", "mdi:camera-outline"),
    _c("plan_day_out", "learning", 11, None, 3, "monthly", "anytime", "mdi:map-outline"),
    _c("library_visit", "learning", 6, None, 2, "every_2_weeks", "anytime", "mdi:library-outline"),
    _c("lego_build", "learning", 4, 12, 1, "weekly", "anytime", "mdi:toy-brick"),
    _c("wipe_spills", "tidy", 3, None, 1, "daily", "anytime", "mdi:water-off-outline"),
    _c("carry_plate", "kitchen", 3, None, 1, "daily", "evening", "mdi:silverware"),
    _c("books_on_shelf", "tidy", 3, 10, 1, "daily", "evening", "mdi:bookshelf"),
    _c("hands_after_toilet", "health", 3, 8, 1, "daily", "anytime", "mdi:hand-wash"),
    _c("please_thank_you", "family", 3, 8, 1, "daily", "anytime", "mdi:hand-heart"),
]


def _top_pick(s: dict) -> dict:
    lo = AGE_GROUP_INFO[s["age_group"]]["min_age"]
    out = _c(
        s["id"],
        _TOP_PICK_CATEGORY[s["id"]],
        lo,
        _TOP_PICK_MAX_AGE.get(s["id"]),
        s["points"],
        s["frequency"],
        s["time_category"],
        s["icon"],
        s["days"],
    )
    out["top_pick"] = True
    return out


LIBRARY_CHORES: list[dict] = [_top_pick(s) for s in SUGGESTED_CHORES] + [
    {**c, "top_pick": False} for c in LIBRARY_EXTRA_CHORES
]

# Starter rewards in three tiers. ``picked`` ones are ticked when the wizard opens.
REWARD_TIERS: tuple[str, ...] = ("small", "saving", "big")
STARTER_REWARDS: list[dict] = [
    {"id": "screen_time", "tier": "small", "cost": 15, "icon": "mdi:television-play", "picked": True},
    {"id": "pick_pudding", "tier": "small", "cost": 10, "icon": "mdi:cupcake", "picked": False},
    {"id": "car_music", "tier": "small", "cost": 10, "icon": "mdi:music", "picked": False},
    {"id": "choose_dinner", "tier": "saving", "cost": 40, "icon": "mdi:pizza", "picked": True},
    {"id": "stay_up_late", "tier": "saving", "cost": 40, "icon": "mdi:weather-night", "picked": True},
    {"id": "family_film", "tier": "saving", "cost": 30, "icon": "mdi:movie-open-outline", "picked": True},
    {"id": "ice_cream_trip", "tier": "big", "cost": 100, "icon": "mdi:ice-cream", "picked": True},
    {"id": "spending_money", "tier": "big", "cost": 150, "icon": "mdi:cash", "picked": False},
    {"id": "sleepover", "tier": "big", "cost": 250, "icon": "mdi:sleep", "picked": True},
]


# Starter rewards are the reward library's top picks; these are the rest. Each
# cost is a fixed starting value the parent can change before adding.
_STARTER_MIN_AGE: dict[str, int] = {"spending_money": 7, "sleepover": 7}
LIBRARY_EXTRA_REWARDS: list[dict] = [
    {"id": "sweet_treat", "tier": "small", "cost": 8, "icon": "mdi:candy-outline", "min_age": 3},
    {"id": "gaming_30", "tier": "small", "cost": 25, "icon": "mdi:gamepad-variant-outline", "min_age": 7},
    {"id": "bubble_bath", "tier": "small", "cost": 10, "icon": "mdi:bathtub-outline", "min_age": 3},
    {"id": "extra_story", "tier": "small", "cost": 10, "icon": "mdi:book-open-variant", "min_age": 3},
    {"id": "choose_breakfast", "tier": "small", "cost": 12, "icon": "mdi:food-croissant", "min_age": 4},
    {"id": "sticker_sheet", "tier": "small", "cost": 10, "icon": "mdi:sticker-emoji", "min_age": 3},
    {"id": "choose_seat", "tier": "small", "cost": 8, "icon": "mdi:seat-outline", "min_age": 4},
    {"id": "fizzy_drink", "tier": "small", "cost": 12, "icon": "mdi:bottle-soda-outline", "min_age": 6},
    {"id": "video_call_friend", "tier": "small", "cost": 15, "icon": "mdi:video-outline", "min_age": 9},
    {"id": "skip_chore", "tier": "small", "cost": 30, "icon": "mdi:debug-step-over", "min_age": 8},
    {"id": "breakfast_in_bed", "tier": "saving", "cost": 50, "icon": "mdi:coffee-outline", "min_age": 5},
    {"id": "living_room_camp", "tier": "saving", "cost": 80, "icon": "mdi:tent", "min_age": 5},
    {"id": "bowling", "tier": "saving", "cost": 120, "icon": "mdi:bowling", "min_age": 6},
    {"id": "climbing_wall", "tier": "saving", "cost": 150, "icon": "mdi:carabiner", "min_age": 8},
    {"id": "pool_trip", "tier": "saving", "cost": 80, "icon": "mdi:swim", "min_age": 4},
    {"id": "karaoke_night", "tier": "saving", "cost": 60, "icon": "mdi:microphone-variant", "min_age": 6},
    {"id": "one_to_one", "tier": "saving", "cost": 70, "icon": "mdi:account-heart-outline", "min_age": 3},
    {"id": "lunch_out", "tier": "saving", "cost": 120, "icon": "mdi:food", "min_age": 6},
    {"id": "new_book", "tier": "saving", "cost": 90, "icon": "mdi:bookshelf", "min_age": 4},
    {"id": "bake_cake", "tier": "saving", "cost": 50, "icon": "mdi:cake-variant-outline", "min_age": 4},
    {"id": "friend_for_tea", "tier": "saving", "cost": 80, "icon": "mdi:account-multiple-outline", "min_age": 5},
    {"id": "big_park", "tier": "saving", "cost": 40, "icon": "mdi:slide", "min_age": 3},
    {"id": "theme_park", "tier": "big", "cost": 600, "icon": "mdi:ferris-wheel", "min_age": 7},
    {"id": "zoo_trip", "tier": "big", "cost": 400, "icon": "mdi:elephant", "min_age": 4},
    {"id": "show_trip", "tier": "big", "cost": 450, "icon": "mdi:drama-masks", "min_age": 5},
    {"id": "new_game", "tier": "big", "cost": 500, "icon": "mdi:controller", "min_age": 9},
    {"id": "new_toy", "tier": "big", "cost": 350, "icon": "mdi:teddy-bear", "min_age": 3},
    {"id": "towards_trainers", "tier": "big", "cost": 400, "icon": "mdi:shoe-sneaker", "min_age": 11},
    {"id": "cinema_friend", "tier": "big", "cost": 250, "icon": "mdi:popcorn", "min_age": 8},
    {"id": "shopping_trip", "tier": "big", "cost": 350, "icon": "mdi:shopping-outline", "min_age": 11},
    {"id": "day_out_choice", "tier": "big", "cost": 500, "icon": "mdi:map-marker-star-outline", "min_age": 5},
    {"id": "camping_weekend", "tier": "big", "cost": 700, "icon": "mdi:campfire", "min_age": 7},
    {"id": "takeaway_night", "tier": "big", "cost": 200, "icon": "mdi:food-takeout-box-outline", "min_age": 6},
    {"id": "friend_day_out", "tier": "big", "cost": 400, "icon": "mdi:account-group-outline", "min_age": 10},
    {"id": "phone_data", "tier": "big", "cost": 200, "icon": "mdi:signal-cellular-3", "min_age": 13},
    {"id": "late_weekend", "tier": "saving", "cost": 60, "icon": "mdi:weather-night", "min_age": 9},
]
LIBRARY_REWARDS: list[dict] = [
    {
        "id": r["id"],
        "tier": r["tier"],
        "cost": r["cost"],
        "icon": r["icon"],
        "min_age": _STARTER_MIN_AGE.get(r["id"], 3),
        "top_pick": True,
    }
    for r in STARTER_REWARDS
] + [{**r, "top_pick": False} for r in LIBRARY_EXTRA_REWARDS]


def suggestion_schedule(suggestion: dict) -> dict[str, Any]:
    """The chore schedule fields for a suggestion, plus its times-per-week."""
    freq = FREQUENCIES[suggestion["frequency"]]
    days = list(suggestion.get("days") or [])
    schedule: dict[str, Any] = {"schedule_mode": freq["schedule_mode"], "due_days": []}
    if suggestion["frequency"] == "weekdays":
        schedule["due_days"] = list(_WEEKDAYS)
    elif suggestion["frequency"] == "days":
        schedule["due_days"] = days
    if freq["schedule_mode"] == "recurring":
        schedule["recurrence"] = freq["recurrence"]
        # A weekly or fortnightly job pinned to a day only opens on that day.
        schedule["recurrence_day"] = days[0] if days and freq["recurrence"] != "monthly" else ""
    per_week = freq["per_week"] if freq["per_week"] is not None else len(days)
    return {"schedule": schedule, "per_week": per_week}


def setup_catalogue() -> dict[str, Any]:
    """Everything the wizard offers, in the shape the panel uses."""
    return {
        "age_groups": [{"id": gid, **AGE_GROUP_INFO[gid]} for gid in AGE_GROUPS],
        "chores": [{**s, **suggestion_schedule(s)} for s in SUGGESTED_CHORES],
        "reward_tiers": list(REWARD_TIERS),
        "rewards": [dict(r) for r in STARTER_REWARDS],
        "library": library_catalogue(),
    }


def library_catalogue() -> dict[str, Any]:
    """The 📚 library: every chore and reward, by category, with the packs."""
    return {
        "categories": list(CHORE_CATEGORIES),
        "chores": [{**c, **suggestion_schedule(c)} for c in LIBRARY_CHORES],
        "rewards": [dict(r) for r in LIBRARY_REWARDS],
        "packs": [
            {"id": t["id"], "name": t["name"], "icon": t.get("icon", ""), "chores": [dict(c) for c in t["chores"]]}
            for t in BUILT_IN_TEMPLATES
        ],
    }
