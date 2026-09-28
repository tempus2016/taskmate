"""Chore auctions (#982) mixin for TaskMateCoordinator.

A parent opens a reverse auction on one scheduled occurrence of an existing
chore ("Clean the bathroom, Sat 4 Oct") with a maximum price and a closing
time. The eligible children place sealed bids — the fewest points they would
do it for. At closing the lowest bid wins, the earliest bid breaking a tie
(changing a bid re-times it, so it goes to the back of that queue). No bids
leaves the chore on its normal assignment.

How a win overrides one occurrence
----------------------------------
The chore record is never edited. A closed auction with a winner *is* the
override: ``auction_award(chore, day)`` looks it up by (chore id, date) and
the read-time assignment paths consult it, the same way a calendar move
(#977) is read from ``moved_occurrences``:

* ``_compute_active_children`` returns just the winner for that day, ahead
  of every assignment mode's own logic — so rotation, the midnight
  ``assignment_current_child_id`` rewrite, the HA calendar, reminders and the
  cards' availability matrix all follow it.
* ``is_chore_available_for_child`` hides the occurrence from everyone else,
  which also covers "everyone" chores (they have no single active child).
* ``async_complete_chore`` prices the winner's completion that day at the
  winning bid instead of the chore's points; approval then pays it like any
  chore (the streak/weekend multipliers ride on top, as for a parent's
  points override).
* Mandatory misses and the streak's "due today" set ask the same question
  for the day they are judging, so the winner owes it and nobody else does.

A win is keyed by the occurrence's scheduled date. If that occurrence is later
moved on the calendar, the lookup follows it via ``occurrence_origin``.
Deleting the winner (or cancelling the auction) simply makes the lookup miss,
and the chore falls back to its normal assignment.

Closing runs on a point-in-time timer armed for the next deadline, with the
coordinator's 30 s tick and startup as the backstop (an auction whose closing
time passed while HA was off is settled on the next start).

Bids are secret. Only a parent (the admin panel, or a parent user through
``taskmate/auctions/list``) ever sees amounts; a child's view carries the
number of bids, their own bid, and after closing the winner and price.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.util import dt as dt_util

from .const import (
    AUCTION_POINTS_MAX,
    AUCTION_REMINDER_MINUTES,
    AUCTION_RESULTS_HOURS,
    NOTIF_TYPE_AUCTION_CLOSING,
    NOTIF_TYPE_AUCTION_OPENED,
    NOTIF_TYPE_AUCTION_RESULT,
)
from .coord_bounties import parse_bounty_expiry
from .models import Auction, format_datetime

_LOGGER = logging.getLogger(__name__)

# How far ahead the panel offers occurrences to auction, and how many.
_OCCURRENCE_HORIZON_DAYS = 60
_OCCURRENCE_LIMIT = 6


def _short_date(day: date) -> str:
    """A short date like "Sat 4 Oct", for push messages (rendered server-side)."""
    return f"{day.strftime('%a')} {day.day} {day.strftime('%b')}"


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class AuctionsMixin:
    """Mixin providing chore auctions."""

    # ── the override: who does an occurrence, and for how much ───────────

    def _auction_awards(self) -> dict[tuple[str, str], tuple[str, int]]:
        """{(chore_id, ISO date): (winner_id, price)} for every won auction.

        Read from the raw store (no dataclass rebuild) because the assignment
        paths ask per chore × child and per chore × day. Memoised inside an
        availability build scope, where storage cannot change.
        """
        cache = getattr(self, "_avail_cache", None)
        if cache is not None and "auction_awards" in cache:
            return cache["auction_awards"]
        data = getattr(getattr(self, "storage", None), "data", None)
        raw = data.get("auctions") if isinstance(data, dict) else None
        awards: dict[tuple[str, str], tuple[str, int]] = {}
        for item in raw if isinstance(raw, list) else ():
            if isinstance(item, dict) and item.get("status") == "closed" and item.get("winner_id"):
                key = (str(item.get("chore_id") or ""), str(item.get("occurrence") or ""))
                awards[key] = (str(item["winner_id"]), max(0, _as_int(item.get("price"))))
        if cache is not None:
            cache["auction_awards"] = awards
        return awards

    def auction_award(self, chore, day: date | None = None) -> tuple[str, int] | None:
        """(winner_id, price) when ``chore``'s occurrence on ``day`` was won at
        auction, else None. ``day`` defaults to today.

        A win whose winner has since been deleted no longer applies, so the
        chore falls back to its normal assignment.
        """
        awards = self._auction_awards()
        if not awards:
            return None
        if day is None:
            day = dt_util.as_local(dt_util.now()).date()
        hit = awards.get((chore.id, day.isoformat()))
        if hit is None:
            # The auctioned occurrence was moved on the calendar (#977): the
            # win travels with it.
            origin = self.occurrence_origin(chore, day)
            if origin != day:
                hit = awards.get((chore.id, origin.isoformat()))
        if hit is None or self._cached_child(hit[0]) is None:
            return None
        return hit

    def auction_winner(self, chore, day: date | None = None) -> str:
        """The child who won ``chore``'s occurrence on ``day``, or ""."""
        award = self.auction_award(chore, day)
        return award[0] if award else ""

    def auction_price_for(self, chore, child_id: str, day: date | None = None) -> int | None:
        """The winning bid ``child_id`` is owed for ``chore`` on ``day``, if any."""
        award = self.auction_award(chore, day)
        if award and award[0] == child_id:
            return award[1]
        return None

    def auction_wins_for_chore(self, chore, start: date, days: int) -> dict[str, dict]:
        """Won occurrences of ``chore`` in [start, start + days): the cards'
        view of the override ({ISO date: {"child_id", "points"}})."""
        if not self._auction_awards():
            return {}
        out: dict[str, dict] = {}
        for offset in range(days):
            day = start + timedelta(days=offset)
            award = self.auction_award(chore, day)
            if award:
                out[day.isoformat()] = {"child_id": award[0], "points": award[1]}
        return out

    # ── reads ─────────────────────────────────────────────────────────────

    def get_auction(self, auction_id: str) -> Auction | None:
        return self.storage.get_auction(auction_id)

    def _require_auction(self, auction_id: str) -> Auction:
        auction = self.storage.get_auction(auction_id)
        if auction is None:
            raise ValueError("That auction no longer exists. Refresh the card.")
        return auction

    def auction_pool(self, chore) -> list[str]:
        """Children who could be given ``chore``: its pool, or everyone."""
        return list(self._chore_assignment_pool(chore))

    def auction_refusal(self, chore) -> str:
        """Why ``chore`` can't be auctioned, or "" when it can."""
        if not getattr(chore, "enabled", True):
            return "That chore is switched off."
        if getattr(chore, "assignment_mode", "everyone") == "unassigned":
            return "Nobody can be given an unassigned chore, so it can't be auctioned."
        if self.teamwork_size(chore):
            return "A teamwork chore is shared by a team, so it can't be auctioned."
        if getattr(chore, "task_type", "standard") == "timed":
            return "A timed chore is paid by the minute, so it can't be auctioned."
        if getattr(chore, "open_ended", False):
            return "An open-ended chore is priced by the parent, so it can't be auctioned."
        return ""

    def _auction_blocks(self, chore_id: str, occurrence: str, *, ignore_id: str = "") -> bool:
        """True when (chore, occurrence) already has a live or won auction."""
        for a in self.storage.get_auctions():
            if a.id == ignore_id or a.chore_id != chore_id or a.occurrence != occurrence:
                continue
            if a.status == "open" or (a.status == "closed" and a.winner_id):
                return True
        return False

    def auction_occurrences(self, chore_id: str) -> list[str]:
        """The chore's next scheduled dates a parent may auction (tomorrow on)."""
        chore = self.storage.get_chore(chore_id)
        if chore is None or self.auction_refusal(chore):
            return []
        today = dt_util.as_local(dt_util.now()).date()
        out: list[str] = []
        for offset in range(1, _OCCURRENCE_HORIZON_DAYS + 1):
            day = today + timedelta(days=offset)
            if not self._is_chore_scheduled_for_date(chore, day):
                continue
            if self._auction_blocks(chore.id, day.isoformat()):
                continue
            out.append(day.isoformat())
            if len(out) >= _OCCURRENCE_LIMIT:
                break
        return out

    # ── parent: open / close now / cancel ─────────────────────────────────

    async def async_start_auction(
        self,
        chore_id: str,
        occurrence,
        max_points: int,
        closes_at,
        *,
        eligible_child_ids: list[str] | None = None,
        min_points: int = 1,
        notify_children: bool = True,
    ) -> Auction:
        """Open an auction on one occurrence of a chore.

        Bidding must close before the occurrence's day begins, so the winner
        is settled before anyone could have started it. Only one live (or
        won) auction per occurrence; one that closed without bids, or was
        cancelled, can be re-opened — typically with a higher maximum.
        """
        chore = self.storage.get_chore(chore_id)
        if chore is None:
            raise ValueError(f"Chore {chore_id} not found")
        refusal = self.auction_refusal(chore)
        if refusal:
            raise ValueError(refusal)
        try:
            day = occurrence if isinstance(occurrence, date) else date.fromisoformat(str(occurrence).strip())
        except (TypeError, ValueError) as err:
            raise ValueError(f"Invalid date: {occurrence}") from err
        now = dt_util.now()
        today = dt_util.as_local(now).date()
        if day <= today:
            raise ValueError("Pick an occurrence from tomorrow onwards.")
        if not self._is_chore_scheduled_for_date(chore, day):
            raise ValueError(f"'{chore.name}' isn't scheduled on {day.isoformat()}.")
        if self._auction_blocks(chore.id, day.isoformat()):
            raise ValueError("That occurrence already has an auction.")

        try:
            max_points = int(max_points)
            min_points = int(min_points)
        except (TypeError, ValueError) as err:
            raise ValueError("Points must be whole numbers.") from err
        if max_points < 1 or max_points > AUCTION_POINTS_MAX:
            raise ValueError(f"The maximum bid is between 1 and {AUCTION_POINTS_MAX} points.")
        if min_points < 1 or min_points > max_points:
            raise ValueError("The minimum bid must be between 1 and the maximum.")

        closes = parse_bounty_expiry(closes_at)
        if closes is None:
            raise ValueError("An auction needs a closing time.")
        day_starts = datetime.combine(day, time(0, 0), tzinfo=dt_util.DEFAULT_TIME_ZONE)
        if closes <= now:
            raise ValueError("The closing time is already in the past.")
        if closes > day_starts:
            raise ValueError("Bidding must close before the day of the chore.")

        pool = self.auction_pool(chore)
        eligible: list[str] = []
        for child_id in eligible_child_ids or pool:
            if not self.get_child(child_id):
                raise ValueError(f"Child {child_id} not found")
            if child_id not in pool:
                raise ValueError("Only children who can do this chore can bid on it.")
            if child_id not in eligible:
                eligible.append(child_id)
        if not eligible:
            raise ValueError("Pick at least one child who can bid.")

        auction = Auction(
            chore_id=chore.id,
            occurrence=day.isoformat(),
            max_points=max_points,
            min_points=min_points,
            closes_at=closes,
            eligible_child_ids=eligible,
            notify_children=bool(notify_children),
            chore_name=chore.name,
            chore_points=self.effective_chore_points(chore),
            created_at=now,
        )
        self.storage.add_auction(auction)
        await self.storage.async_save()
        self._fire_auction_event("taskmate_auction_opened", auction)
        self._arm_auction_timer()
        await self.async_refresh()
        if auction.notify_children:
            await self.notifications.fire(
                NOTIF_TYPE_AUCTION_OPENED,
                {
                    "chore_name": auction.chore_name,
                    "date": _short_date(day),
                    "max_points": auction.max_points,
                    "points_name": self.storage.get_points_name(),
                },
                only_recipients={f"child:{c}" for c in eligible},
            )
        return auction

    async def async_close_auction(self, auction_id: str) -> Auction:
        """A parent ends bidding now ("Close now") and settles the winner."""
        auction = self._require_auction(auction_id)
        if auction.status != "open":
            raise ValueError("This auction has already closed.")
        self._settle_auction(auction, dt_util.now())
        await self.storage.async_save()
        await self._async_after_auction_closed(auction)
        self._arm_auction_timer()
        await self.async_refresh()
        return auction

    async def async_cancel_auction(self, auction_id: str) -> None:
        """Call an auction off: the occurrence goes back to its normal
        assignment, and anyone who bid is told.

        Works while bidding is open and after it closed with a winner, up to
        the day itself; a past occurrence is history.
        """
        auction = self._require_auction(auction_id)
        if auction.status == "cancelled":
            raise ValueError("This auction was already cancelled.")
        today = dt_util.as_local(dt_util.now()).date()
        if auction.status == "closed" and auction.occurrence < today.isoformat():
            raise ValueError("That occurrence has already happened.")
        bidders = list(auction.bids)
        was_won = auction.status == "closed" and bool(auction.winner_id)
        auction.status = "cancelled"
        auction.winner_id = ""
        auction.price = 0
        auction.closed_at = dt_util.now()
        self.storage.update_auction(auction)
        if was_won:
            self._auction_apply_today(auction)
        await self.storage.async_save()
        self._fire_auction_event("taskmate_auction_cancelled", auction)
        self._arm_auction_timer()
        await self.async_refresh()
        await self._async_tell_bidders_called_off(auction, bidders)

    async def _async_tell_bidders_called_off(self, auction: Auction, bidders: list[str]) -> None:
        """The "called off" push, to the children who bid on ``auction``."""
        if not bidders:
            return
        await self.notifications.fire(
            NOTIF_TYPE_AUCTION_RESULT,
            {
                "chore_name": auction.chore_name,
                "date": self._auction_date_label(auction),
                "result_text": f"the auction for '{auction.chore_name}' was called off. "
                "It goes back to the normal rota.",
            },
            only_recipients={f"child:{c}" for c in bidders},
        )

    def _auction_is_live(self, auction: Auction) -> bool:
        """Still in play: bidding open, or a win whose day hasn't passed."""
        if auction.status == "open":
            return True
        today = dt_util.as_local(dt_util.now()).date().isoformat()
        return auction.status == "closed" and bool(auction.winner_id) and auction.occurrence >= today

    def auction_deletable(self, auction: Auction) -> bool:
        """Finished, so a parent may delete it: cancelled, closed with no
        bids, or a win whose day has passed. A live one is cancelled instead,
        which tells the bidders (#999)."""
        return not self._auction_is_live(auction)

    async def async_delete_auction(self, auction_id: str) -> None:
        """A parent deletes a finished auction from the list (#999)."""
        auction = self._require_auction(auction_id)
        if not self.auction_deletable(auction):
            raise ValueError("This auction is still live. Cancel it instead.")
        self.storage.remove_auction(auction.id)
        await self.storage.async_save()
        await self.async_refresh()

    # ── child: bid / withdraw ─────────────────────────────────────────────

    def _require_open_for(self, auction: Auction, child_id: str) -> None:
        if not self.get_child(child_id):
            raise ValueError(f"Child {child_id} not found")
        if child_id not in auction.eligible_child_ids:
            raise ValueError("This auction isn't for you.")
        if auction.status != "open" or (auction.closes_at is not None and auction.closes_at <= dt_util.now()):
            raise ValueError("Bidding on this auction has closed.")

    async def async_place_bid(self, auction_id: str, child_id: str, points: int) -> Auction:
        """Seal ``child_id``'s bid: the fewest points they'd do it for.

        Changing a bid counts as a new bid, so it moves to the back of the
        tie-break queue. Re-sealing the same number changes nothing.
        """
        auction = self._require_auction(auction_id)
        self._require_open_for(auction, child_id)
        try:
            points = int(points)
        except (TypeError, ValueError) as err:
            raise ValueError("A bid is a whole number of points.") from err
        if points < auction.min_points or points > auction.max_points:
            raise ValueError(f"Bid between {auction.min_points} and {auction.max_points} points.")
        current = auction.bids.get(child_id)
        if current and int(current.get("points", 0)) == points:
            return auction
        auction.bids[child_id] = {"points": points, "at": format_datetime(dt_util.now())}
        self.storage.update_auction(auction)
        await self.storage.async_save()
        # The amount is secret: the event says who bid, never how much.
        self._fire_auction_event("taskmate_auction_bid", auction, child_id)
        await self.async_refresh()
        return auction

    async def async_withdraw_bid(self, auction_id: str, child_id: str) -> Auction:
        """Take ``child_id``'s bid back while bidding is still open."""
        auction = self._require_auction(auction_id)
        self._require_open_for(auction, child_id)
        if child_id not in auction.bids:
            raise ValueError("You haven't bid on this one.")
        del auction.bids[child_id]
        self.storage.update_auction(auction)
        await self.storage.async_save()
        self._fire_auction_event("taskmate_auction_bid_withdrawn", auction, child_id)
        await self.async_refresh()
        return auction

    # ── closing ───────────────────────────────────────────────────────────

    def _settle_auction(self, auction: Auction, now: datetime) -> None:
        """Close ``auction``: lowest bid wins, earliest on a tie. In storage
        only — the caller saves, notifies and refreshes."""
        ranked = [b for b in auction.ranked_bids() if self.get_child(b[0])]
        auction.status = "closed"
        auction.closed_at = now
        if ranked:
            auction.winner_id, auction.price = ranked[0][0], ranked[0][1]
        else:
            auction.winner_id, auction.price = "", 0
        self.storage.update_auction(auction)
        self._auction_apply_today(auction)

    def _auction_apply_today(self, auction: Auction) -> None:
        """Re-point today's rotation pointer when the change lands on today.

        An auction closes before its day starts, so the midnight rotation
        normally picks the winner up. This covers the rest: one settled late
        (HA was off at closing time) or cancelled on the day itself.
        """
        if auction.occurrence != dt_util.as_local(dt_util.now()).date().isoformat():
            return
        chore = self.storage.get_chore(auction.chore_id)
        if chore is None or getattr(chore, "assignment_mode", "everyone") == "everyone":
            return
        desired = self._compute_daily_assignments().get(chore.id, "")
        if getattr(chore, "assignment_current_child_id", "") != desired:
            chore.assignment_current_child_id = desired
            self.storage.update_chore(chore)

    async def _async_after_auction_closed(self, auction: Auction) -> None:
        """Announce a settled auction: bus event and the results push."""
        winner = self.get_child(auction.winner_id) if auction.winner_id else None
        self._fire_auction_event("taskmate_auction_closed", auction, auction.winner_id)
        if winner is not None:
            result = (
                f"{winner.name} won '{auction.chore_name}' on {self._auction_date_label(auction)} "
                f"for {auction.price} {self.storage.get_points_name()}."
            )
        else:
            result = f"no bids for '{auction.chore_name}', so it goes back to the normal rota."
        recipients = {f"child:{c}" for c in auction.eligible_child_ids}
        recipients |= {p.id for p in self.storage.get_parent_recipients()}
        await self.notifications.fire(
            NOTIF_TYPE_AUCTION_RESULT,
            {
                "chore_name": auction.chore_name,
                "date": self._auction_date_label(auction),
                "child_name": getattr(winner, "name", ""),
                "points": auction.price,
                "points_name": self.storage.get_points_name(),
                "result_text": result,
            },
            only_recipients=recipients,
        )

    async def async_sweep_auctions(self, refresh: bool = True) -> bool:
        """Settle auctions whose bidding has ended, and send the one-hour
        reminder. Runs from the closing timer, the coordinator tick and at
        startup (catching up on anything that closed while HA was off).
        ``refresh=False`` when called from inside the refresh itself.
        """
        now = dt_util.now()
        window = timedelta(minutes=AUCTION_REMINDER_MINUTES)
        closed: list[Auction] = []
        reminders: list[Auction] = []
        for auction in self.storage.get_auctions():
            if auction.status != "open":
                continue
            if auction.closes_at is None or auction.closes_at <= now:
                self._settle_auction(auction, now)
                closed.append(auction)
            elif self._auction_reminder_due(auction, now, window):
                auction.reminder_sent = True
                self.storage.update_auction(auction)
                reminders.append(auction)
        if not closed and not reminders:
            return False
        await self.storage.async_save()
        for auction in closed:
            await self._async_after_auction_closed(auction)
        for auction in reminders:
            minutes = max(1, round((auction.closes_at - now).total_seconds() / 60))
            for child_id in auction.eligible_child_ids:
                child = self.get_child(child_id)
                if child is None:
                    continue
                await self.notifications.fire(
                    NOTIF_TYPE_AUCTION_CLOSING,
                    {
                        "child_name": child.name,
                        "child_id": child.id,
                        "chore_name": auction.chore_name,
                        "minutes": minutes,
                    },
                    only_recipients={f"child:{child.id}"},
                )
        self._arm_auction_timer()
        if refresh:
            await self.async_refresh()
        return True

    @staticmethod
    def _auction_reminder_due(auction: Auction, now: datetime, window: timedelta) -> bool:
        if not auction.notify_children or auction.reminder_sent or auction.closes_at is None:
            return False
        if auction.closes_at - now > window:
            return False
        # An auction opened with less than the window to go would "remind"
        # the moment it opened, straight after the "it's open" push.
        return auction.created_at is None or auction.closes_at - auction.created_at > window

    def _next_auction_deadline(self) -> datetime | None:
        """The next closing time or reminder the timer has to wake for."""
        window = timedelta(minutes=AUCTION_REMINDER_MINUTES)
        due: list[datetime] = []
        for auction in self.storage.get_auctions():
            if auction.status != "open" or auction.closes_at is None:
                continue
            due.append(auction.closes_at)
            reminder_at = auction.closes_at - window
            if (
                auction.notify_children
                and not auction.reminder_sent
                and (auction.created_at is None or auction.closes_at - auction.created_at > window)
            ):
                due.append(reminder_at)
        return min(due) if due else None

    def _arm_auction_timer(self) -> None:
        """(Re)arm the one timer that wakes for the next auction deadline."""
        self.cancel_auction_timer()
        due = self._next_auction_deadline()
        if due is None:
            return
        # Never in the past: a deadline that already passed is swept now-ish.
        at = max(due, dt_util.now() + timedelta(seconds=1)).astimezone(timezone.utc)
        self._unsub_auction_timer = async_track_point_in_utc_time(self.hass, self._auction_timer_fired, at)

    def cancel_auction_timer(self) -> None:
        unsub = getattr(self, "_unsub_auction_timer", None)
        if unsub:
            unsub()
        self._unsub_auction_timer = None

    @callback
    def _auction_timer_fired(self, _now: datetime) -> None:
        self._unsub_auction_timer = None
        self.hass.async_create_task(self.async_sweep_auctions())

    # ── housekeeping ──────────────────────────────────────────────────────

    async def async_prune_auctions(self) -> None:
        """Drop finished auctions older than the completion history (midnight)."""
        try:
            days = int(self.storage.get_setting("history_days", "90"))
        except (TypeError, ValueError):
            days = 90
        cutoff = (dt_util.as_local(dt_util.now()).date() - timedelta(days=days)).isoformat()
        stale = [a.id for a in self.storage.get_auctions() if a.status != "open" and a.occurrence < cutoff]
        if not stale:
            return
        for auction_id in stale:
            self.storage.remove_auction(auction_id)
        await self.storage.async_save()

    def remove_child_from_auctions(self, child_id: str) -> None:
        """Follow a deleted child: drop their bids and their eligibility.

        An open auction nobody is left to bid on goes. A win of theirs stops
        applying on its own (``auction_award`` checks the winner exists).
        """
        for auction in self.storage.get_auctions():
            if child_id not in auction.bids and child_id not in auction.eligible_child_ids:
                continue
            if auction.status == "open":
                auction.bids.pop(child_id, None)
                auction.eligible_child_ids = [c for c in auction.eligible_child_ids if c != child_id]
                if not auction.eligible_child_ids:
                    self.storage.remove_auction(auction.id)
                    continue
                self.storage.update_auction(auction)

    def remove_chore_from_auctions(self, chore_id: str) -> list[tuple[Auction, list[str]]]:
        """A deleted chore takes its auctions with it (#999).

        Live ones are cancelled first — the bus event fires here, and the
        caller sends the usual "called off" push to the returned
        ``(auction, bidders)`` pairs once it has saved. In storage only.
        """
        called_off = []
        for auction in self.storage.get_auctions():
            if auction.chore_id != chore_id:
                continue
            if self._auction_is_live(auction):
                bidders = list(auction.bids)
                auction.status = "cancelled"
                auction.winner_id = ""
                auction.price = 0
                auction.closed_at = dt_util.now()
                self._fire_auction_event("taskmate_auction_cancelled", auction)
                called_off.append((auction, bidders))
            self.storage.remove_auction(auction.id)
        if called_off:
            self._arm_auction_timer()
        return called_off

    async def async_remove_orphaned_auctions(self) -> None:
        """On load: drop auctions whose chore no longer exists (#999) — left
        behind by deletes from before auctions followed their chore."""
        chore_ids = {c.id for c in self.storage.get_chores()}
        orphans = [a.id for a in self.storage.get_auctions() if a.chore_id not in chore_ids]
        if not orphans:
            return
        for auction_id in orphans:
            self.storage.remove_auction(auction_id)
        await self.storage.async_save()

    # ── views ─────────────────────────────────────────────────────────────

    def _auction_date_label(self, auction: Auction) -> str:
        try:
            return _short_date(date.fromisoformat(auction.occurrence))
        except ValueError:
            return auction.occurrence

    def _auction_base(self, auction: Auction) -> dict:
        chore = self.storage.get_chore(auction.chore_id)
        out = {
            "id": auction.id,
            "chore_id": auction.chore_id,
            "chore_name": getattr(chore, "name", "") or auction.chore_name,
            "icon": getattr(chore, "icon", "") or "",
            "occurrence": auction.occurrence,
            "max_points": auction.max_points,
            "min_points": auction.min_points,
            "normal_points": auction.chore_points,
            "closes_at": format_datetime(auction.closes_at),
            "status": auction.status,
            "eligible_child_ids": list(auction.eligible_child_ids),
            "bid_count": len(auction.bids),
        }
        if auction.status != "open":
            out["closed_at"] = format_datetime(auction.closed_at)
            out["winner_id"] = auction.winner_id
            out["price"] = auction.price
        return out

    def _auction_recent(self, auction: Auction, now: datetime) -> bool:
        """Open, or closed with a result inside the card's results window."""
        if auction.status == "open":
            return True
        if auction.status != "closed" or auction.closed_at is None:
            return False
        return now - auction.closed_at <= timedelta(hours=AUCTION_RESULTS_HOURS)

    def auctions_public_state(self) -> list[dict]:
        """What anyone may see (the auctions sensor): no bid amounts, no
        bidders — just how many bids are in, and the result once closed."""
        now = dt_util.now()
        out = []
        for auction in self.storage.get_auctions():
            if not self._auction_recent(auction, now):
                continue
            row = {
                "id": auction.id,
                "chore_id": auction.chore_id,
                "occurrence": auction.occurrence,
                "closes_at": format_datetime(auction.closes_at),
                "status": auction.status,
                "bids": len(auction.bids),
                "eligible": list(auction.eligible_child_ids),
            }
            if auction.status == "closed":
                row["winner_id"] = auction.winner_id
                row["price"] = auction.price
            out.append(row)
        return out

    def auctions_for_child(self, child_id: str) -> list[dict]:
        """A child's card: the auctions they may bid on and recent results.

        Their own bid only — never anyone else's amount.
        """
        now = dt_util.now()
        out = []
        for auction in self.storage.get_auctions():
            if child_id not in auction.eligible_child_ids or not self._auction_recent(auction, now):
                continue
            # A "no bids" result is stale once the occurrence is re-auctioned
            # (or that re-run was won): show the live one, not both.
            if (
                auction.status == "closed"
                and not auction.winner_id
                and self._auction_blocks(auction.chore_id, auction.occurrence, ignore_id=auction.id)
            ):
                continue
            row = self._auction_base(auction)
            mine = auction.bids.get(child_id)
            row["my_bid"] = int(mine["points"]) if mine else None
            out.append(row)
        return out

    def auctions_state(self) -> list[dict]:
        """Every auction for a parent — bid amounts, ranking and, for a won
        occurrence, how the chore itself is going."""
        today = dt_util.as_local(dt_util.now()).date().isoformat()
        completions = None
        out = []
        for auction in self.storage.get_auctions():
            row = self._auction_base(auction)
            row["created_at"] = format_datetime(auction.created_at)
            row["notify_children"] = auction.notify_children
            row["deletable"] = self.auction_deletable(auction)
            row["bids"] = [
                {"child_id": cid, "points": pts, "at": format_datetime(at)} for cid, pts, at in auction.ranked_bids()
            ]
            if auction.status == "closed" and auction.winner_id:
                if completions is None:
                    completions = self.storage.get_completions()
                row["chore_status"], row["points_awarded"] = self._auction_chore_status(auction, completions, today)
            out.append(row)
        return out

    @staticmethod
    def _auction_chore_status(auction: Auction, completions: list, today: str) -> tuple[str, int]:
        """done / pending / missed / todo for the winner's occurrence."""
        pending = False
        for comp in completions:
            if comp.chore_id != auction.chore_id or comp.child_id != auction.winner_id:
                continue
            if getattr(comp, "bonus_subtask_id", ""):
                continue
            try:
                if dt_util.as_local(comp.completed_at).date().isoformat() != auction.occurrence:
                    continue
            except (AttributeError, TypeError, ValueError):
                continue
            if comp.approved:
                return "done", int(comp.points_awarded or 0)
            pending = True
        if pending:
            return "pending", 0
        return ("missed" if auction.occurrence < today else "todo"), 0

    def _fire_auction_event(self, event: str, auction: Auction, child_id: str = "") -> None:
        child = self.get_child(child_id) if child_id else None
        payload = {
            "auction_id": auction.id,
            "chore_id": auction.chore_id,
            "chore_name": auction.chore_name,
            "occurrence": auction.occurrence,
            "max_points": auction.max_points,
            "bid_count": len(auction.bids),
            "child_id": child_id,
            "child_name": getattr(child, "name", ""),
            "timestamp": dt_util.now().isoformat(),
        }
        if event == "taskmate_auction_closed":
            payload["price"] = auction.price
        self.hass.bus.async_fire(event, payload)
