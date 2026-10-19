"""``taskmate.*`` services for help requests, moods, sick days, weekly goals, raffles and pets.

Kept out of ``__init__.py`` like the wishlist and inspection services. A child
may ask for help, log a mood, set their own weekly goal and buy raffle
tickets for themselves (through the same linked-child gate as completing a
chore); answering help, sick days and running raffles are parent actions.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coord_appeals import APPEAL_KINDS, APPEAL_MESSAGE_MAX, APPEAL_NOTE_MAX
from .coord_boosts import BOOST_MAX_MINUTES, BOOST_MAX_MULTIPLIER, BOOST_MIN_MULTIPLIER, BOOST_NAME_MAX
from .coord_goals import WEEKLY_GOAL_MAX
from .coord_pets import PET_NAME_MAX, PET_SPECIES
from .coord_wellbeing import HELP_MESSAGE_MAX, MOODS

_LOGGER = logging.getLogger(__name__)

SERVICE_REQUEST_HELP = "request_help"
SERVICE_ANSWER_HELP = "answer_help"
SERVICE_LOG_MOOD = "log_mood"
SERVICE_SET_SICK_DAY = "set_sick_day"
SERVICE_SET_WEEKLY_GOAL = "set_weekly_goal"
SERVICE_BUY_RAFFLE_TICKETS = "buy_raffle_tickets"
SERVICE_DRAW_RAFFLE = "draw_raffle"
SERVICE_ADOPT_PET = "adopt_pet"
SERVICE_MARK_REWARD_DELIVERED = "mark_reward_delivered"
SERVICE_START_BOOST = "start_boost"
SERVICE_APPEAL = "appeal"
SERVICE_DECIDE_APPEAL = "decide_appeal"
SERVICE_END_BOOST = "end_boost"

FAMILY_SERVICES: tuple[str, ...] = (
    SERVICE_MARK_REWARD_DELIVERED,
    SERVICE_START_BOOST,
    SERVICE_END_BOOST,
    SERVICE_APPEAL,
    SERVICE_DECIDE_APPEAL,
    SERVICE_REQUEST_HELP,
    SERVICE_ANSWER_HELP,
    SERVICE_LOG_MOOD,
    SERVICE_SET_SICK_DAY,
    SERVICE_SET_WEEKLY_GOAL,
    SERVICE_BUY_RAFFLE_TICKETS,
    SERVICE_DRAW_RAFFLE,
    SERVICE_ADOPT_PET,
)

Handler = Callable[[ServiceCall], Awaitable[None]]
Wrapper = Callable[[Handler], Handler]


def async_register_family_services(
    hass: HomeAssistant,
    *,
    child_action: Wrapper,
    parent_action: Wrapper,
    get_coordinator: Callable[[], object],
    require_linked_child: Callable[..., Awaitable[None]],
    require_parent: Callable[..., Awaitable[None]] | None = None,
) -> None:
    """Register the services behind the caller's child and parent gates."""

    def _wrap(action, *, child: bool):
        async def handler(call: ServiceCall) -> None:
            coordinator = get_coordinator()
            if not coordinator:
                _LOGGER.error("No TaskMate coordinator available")
                return
            if child:
                await require_linked_child(hass, call, coordinator, call.data["child_id"])
            await action(coordinator, call)

        return child_action(handler) if child else parent_action(handler)

    async def request_help(coordinator, call):
        await coordinator.async_request_help(call.data["child_id"], call.data["chore_id"], call.data.get("message", ""))

    async def answer_help(coordinator, call):
        await coordinator.async_answer_help(call.data["request_id"])

    async def log_mood(coordinator, call):
        await coordinator.async_log_mood(call.data["child_id"], call.data["mood"])

    async def set_sick_day(coordinator, call):
        await coordinator.async_set_sick_day(call.data["child_id"], call.data.get("date"), call.data.get("sick", True))

    async def set_weekly_goal(coordinator, call):
        await coordinator.async_set_weekly_goal(call.data["child_id"], call.data["target"])

    async def buy_raffle_tickets(coordinator, call):
        await coordinator.async_buy_raffle_tickets(call.data["raffle_id"], call.data["child_id"], call.data["tickets"])

    async def adopt_pet(coordinator, call):
        await coordinator.async_adopt_pet(
            call.data["child_id"], call.data["species"], call.data["name"], hatch_egg=call.data.get("hatch_egg", False)
        )

    async def draw_raffle(coordinator, call):
        await coordinator.async_draw_raffle(call.data["raffle_id"])

    async def start_boost(coordinator, call):
        await coordinator.async_start_boost(
            multiplier=call.data["multiplier"],
            minutes=call.data["minutes"],
            chore_ids=call.data.get("chore_ids") or [],
            child_ids=call.data.get("child_ids") or [],
            starts_at=call.data.get("starts_at"),
            name=call.data.get("name", ""),
            notify=call.data.get("notify", True),
        )

    async def end_boost(coordinator, call):
        await coordinator.async_end_boost(call.data["boost_id"])

    async def appeal(coordinator, call):
        await coordinator.async_appeal(
            call.data["child_id"], call.data["kind"], call.data["target_id"], call.data.get("message", "")
        )

    async def decide_appeal(coordinator, call):
        await coordinator.async_decide_appeal(call.data["appeal_id"], call.data["overturn"], call.data.get("note", ""))

    # Reward fulfilment (#1098): a parent marks a reward handed over, or the
    # child confirms their own with ``child_id`` — so the one service has two
    # gates and picks by who is calling.
    async def mark_reward_delivered(call: ServiceCall) -> None:
        coordinator = get_coordinator()
        if not coordinator:
            _LOGGER.error("No TaskMate coordinator available")
            return
        child_id = call.data.get("child_id")
        if child_id:
            await require_linked_child(hass, call, coordinator, child_id)
            await coordinator.async_mark_reward_delivered(call.data["claim_id"], by="child", child_id=child_id)
            return
        if require_parent is not None:
            await require_parent(hass, call)
        await coordinator.async_mark_reward_delivered(call.data["claim_id"])

    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_REWARD_DELIVERED,
        child_action(mark_reward_delivered),
        schema=vol.Schema({vol.Required("claim_id"): cv.string, vol.Optional("child_id"): cv.string}),
    )

    registrations = (
        (
            SERVICE_REQUEST_HELP,
            request_help,
            True,
            {
                vol.Required("child_id"): cv.string,
                vol.Required("chore_id"): cv.string,
                vol.Optional("message", default=""): vol.All(cv.string, vol.Length(max=HELP_MESSAGE_MAX)),
            },
        ),
        (SERVICE_ANSWER_HELP, answer_help, False, {vol.Required("request_id"): cv.string}),
        (
            SERVICE_LOG_MOOD,
            log_mood,
            True,
            {vol.Required("child_id"): cv.string, vol.Required("mood"): vol.In(MOODS)},
        ),
        (
            SERVICE_SET_SICK_DAY,
            set_sick_day,
            False,
            {
                vol.Required("child_id"): cv.string,
                vol.Optional("date"): cv.date,
                vol.Optional("sick", default=True): cv.boolean,
            },
        ),
        (
            SERVICE_SET_WEEKLY_GOAL,
            set_weekly_goal,
            True,
            {
                vol.Required("child_id"): cv.string,
                vol.Required("target"): vol.All(vol.Coerce(int), vol.Range(min=0, max=WEEKLY_GOAL_MAX)),
            },
        ),
        (
            SERVICE_BUY_RAFFLE_TICKETS,
            buy_raffle_tickets,
            True,
            {
                vol.Required("raffle_id"): cv.string,
                vol.Required("child_id"): cv.string,
                vol.Required("tickets"): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
            },
        ),
        (SERVICE_DRAW_RAFFLE, draw_raffle, False, {vol.Required("raffle_id"): cv.string}),
        (
            SERVICE_START_BOOST,
            start_boost,
            False,
            {
                vol.Required("multiplier"): vol.All(
                    vol.Coerce(float), vol.Range(min=BOOST_MIN_MULTIPLIER, max=BOOST_MAX_MULTIPLIER)
                ),
                vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=BOOST_MAX_MINUTES)),
                vol.Optional("chore_ids", default=[]): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional("child_ids", default=[]): vol.All(cv.ensure_list, [cv.string]),
                vol.Optional("starts_at"): cv.datetime,
                vol.Optional("name", default=""): vol.All(cv.string, vol.Length(max=BOOST_NAME_MAX)),
                vol.Optional("notify", default=True): cv.boolean,
            },
        ),
        (SERVICE_END_BOOST, end_boost, False, {vol.Required("boost_id"): cv.string}),
        (
            SERVICE_APPEAL,
            appeal,
            True,
            {
                vol.Required("child_id"): cv.string,
                vol.Required("kind"): vol.In(APPEAL_KINDS),
                vol.Required("target_id"): cv.string,
                vol.Optional("message", default=""): vol.All(cv.string, vol.Length(max=APPEAL_MESSAGE_MAX)),
            },
        ),
        (
            SERVICE_DECIDE_APPEAL,
            decide_appeal,
            False,
            {
                vol.Required("appeal_id"): cv.string,
                vol.Required("overturn"): cv.boolean,
                vol.Optional("note", default=""): vol.All(cv.string, vol.Length(max=APPEAL_NOTE_MAX)),
            },
        ),
        (
            SERVICE_ADOPT_PET,
            adopt_pet,
            True,
            {
                vol.Required("child_id"): cv.string,
                vol.Required("species"): vol.In(PET_SPECIES),
                vol.Required("name"): vol.All(cv.string, vol.Length(min=1, max=PET_NAME_MAX)),
                vol.Optional("hatch_egg", default=False): cv.boolean,
            },
        ),
    )
    for name, action, child, schema in registrations:
        hass.services.async_register(DOMAIN, name, _wrap(action, child=child), schema=vol.Schema(schema))
