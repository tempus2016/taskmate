"""Bounty board (#931) mixin for TaskMateCoordinator.

A bounty is a one-off job a parent posts for a fixed number of points. Any
eligible child may claim it, which locks it to them for ``claim_hours`` (never
past the bounty's expiry). Done submits a ``ChoreCompletion`` carrying
``bounty_id`` into the ordinary approval queue, so the approvals card, the
panel queue, points, streaks, badges and undo all treat it like a chore; the
chore paths call back into the ``_bounty_on_*`` hooks here to move the bounty
along. A claim that runs out returns the bounty to the board; an unclaimed
bounty vanishes at its expiry. Both are checked on the coordinator's 30 s tick
and at startup.

Lifecycle: open -> claimed -> pending -> completed, with claimed -> open on a
give-back, release or lapse, pending -> claimed (same child) on a reject or the
child's own undo, and open -> expired.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

from . import photos
from .chore_undo import undo_window_seconds
from .const import (
    BOUNTY_CLAIM_HOURS_DEFAULT,
    BOUNTY_CLAIM_HOURS_MAX,
    BOUNTY_DESCRIPTION_MAX_LENGTH,
    BOUNTY_LAPSE_WARNING_MINUTES,
    BOUNTY_POINTS_MAX,
    BOUNTY_TITLE_MAX_LENGTH,
)
from .models import Bounty, Chore, ChoreCompletion

_LOGGER = logging.getLogger(__name__)

# Once a bounty is claimed, only these can still change: the claimer took it
# on for a job, a price and a deadline, so the job itself stays put.
_CLAIMED_EDITABLE = frozenset({"points", "expires_at"})


def parse_bounty_expiry(value) -> datetime | None:
    """A bounty expiry from a service/WS value: None/"" = no expiry.

    Accepts a datetime or an ISO string. A naive time is read as local time —
    it is what a parent typed into a date picker.
    """
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip())
        except (TypeError, ValueError) as err:
            raise ValueError(f"Invalid expiry time: {value}") from err
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
    return parsed


class BountiesMixin:
    """Mixin providing the bounty board."""

    # ── reads ─────────────────────────────────────────────────────────────

    def get_bounty(self, bounty_id: str) -> Bounty | None:
        return self.storage.get_bounty(bounty_id)

    def _require_bounty(self, bounty_id: str) -> Bounty:
        bounty = self.storage.get_bounty(bounty_id)
        if bounty is None:
            raise ValueError("That bounty no longer exists. Refresh the card.")
        return bounty

    def active_bounty_claim(self, child_id: str) -> Bounty | None:
        """The bounty ``child_id`` is currently working on, if any."""
        return next(
            (b for b in self.storage.get_bounties() if b.status == "claimed" and b.claimed_by == child_id),
            None,
        )

    def _bounty_lock_until(self, bounty: Bounty, start: datetime, *, cap_at_expiry: bool = True) -> datetime:
        """When a claim made at ``start`` runs out: the lock, or the expiry if sooner."""
        until = start + timedelta(hours=bounty.claim_hours)
        if cap_at_expiry and bounty.expires_at is not None and bounty.expires_at < until:
            until = bounty.expires_at
        return until

    def bounty_completion_chore(self, completion) -> Chore | None:
        """A stand-in chore for a bounty's completion, for the approval path.

        The chore approval code reads a handful of chore fields (name, points,
        schedule mode). A bounty is not a chore and never enters the chore
        list — this only lets the one shared approval path price and pay it.
        """
        bounty_id = getattr(completion, "bounty_id", "") or ""
        if not bounty_id:
            return None
        bounty = self.storage.get_bounty(bounty_id)
        if bounty is None:
            return None
        return Chore(name=bounty.title, points=bounty.points, id=bounty.id, requires_approval=True)

    # ── parent: post / update / remove / release ─────────────────────────

    def _clean_bounty_fields(self, fields: dict) -> dict:
        """Validate and normalise the editable fields of a bounty."""
        out: dict = {}
        if "title" in fields:
            title = str(fields["title"] or "").strip()
            if not title:
                raise ValueError("A bounty needs a title.")
            out["title"] = title[:BOUNTY_TITLE_MAX_LENGTH]
        if "description" in fields:
            out["description"] = str(fields["description"] or "").strip()[:BOUNTY_DESCRIPTION_MAX_LENGTH]
        if "points" in fields:
            try:
                points = int(fields["points"])
            except (TypeError, ValueError) as err:
                raise ValueError("Points must be a whole number.") from err
            if points < 1 or points > BOUNTY_POINTS_MAX:
                raise ValueError(f"A bounty is worth between 1 and {BOUNTY_POINTS_MAX} points.")
            out["points"] = points
        if "icon" in fields:
            out["icon"] = str(fields["icon"] or "").strip() or "mdi:flag-outline"
        if "expires_at" in fields:
            out["expires_at"] = parse_bounty_expiry(fields["expires_at"])
        if "eligible_child_ids" in fields:
            ids = []
            for child_id in fields["eligible_child_ids"] or []:
                if not self.get_child(child_id):
                    raise ValueError(f"Child {child_id} not found")
                if child_id not in ids:
                    ids.append(child_id)
            # Every child ticked is the same as "all children" — and keeps a
            # child added later eligible, which is what "all" meant.
            if ids and set(ids) == {c.id for c in self.storage.get_children()}:
                ids = []
            out["eligible_child_ids"] = ids
        if "claim_hours" in fields:
            try:
                hours = int(fields["claim_hours"])
            except (TypeError, ValueError) as err:
                raise ValueError("Claim lock must be a whole number of hours.") from err
            if hours < 1 or hours > BOUNTY_CLAIM_HOURS_MAX:
                raise ValueError(f"The claim lock is between 1 and {BOUNTY_CLAIM_HOURS_MAX} hours.")
            out["claim_hours"] = hours
        if "require_photo" in fields:
            out["require_photo"] = bool(fields["require_photo"])
        if "notify_children" in fields:
            out["notify_children"] = bool(fields["notify_children"])
        return out

    async def async_post_bounty(
        self,
        title: str,
        points: int,
        *,
        description: str = "",
        icon: str = "mdi:flag-outline",
        expires_at=None,
        eligible_child_ids: list[str] | None = None,
        claim_hours: int = BOUNTY_CLAIM_HOURS_DEFAULT,
        require_photo: bool = False,
        notify_children: bool = True,
    ) -> Bounty:
        """Put a new bounty on the board and, if asked, tell the eligible children."""
        fields = self._clean_bounty_fields(
            {
                "title": title,
                "points": points,
                "description": description,
                "icon": icon,
                "expires_at": expires_at,
                "eligible_child_ids": eligible_child_ids or [],
                "claim_hours": claim_hours,
                "require_photo": require_photo,
                "notify_children": notify_children,
            }
        )
        now = dt_util.now()
        if fields["expires_at"] is not None and fields["expires_at"] <= now:
            raise ValueError("The expiry is already in the past.")
        bounty = Bounty(**fields, created_at=now)
        self.storage.add_bounty(bounty)
        await self.storage.async_save()
        self.hass.bus.async_fire(
            "taskmate_bounty_posted",
            {"bounty_id": bounty.id, "title": bounty.title, "points": bounty.points},
        )
        await self.async_refresh()
        if bounty.notify_children:
            children = [c for c in self.storage.get_children() if bounty.is_eligible(c.id)]
            if children:
                await self.notifications.fire(
                    "bounty_posted",
                    {
                        "bounty_name": bounty.title,
                        "points": bounty.points,
                        "points_name": self.storage.get_points_name(),
                    },
                    only_recipients={f"child:{c.id}" for c in children},
                )
        return bounty

    async def async_update_bounty(self, bounty_id: str, **changes) -> Bounty:
        """Edit a bounty. Anything goes while it's open; once claimed, only
        points and expiry — and the claimer's lock is re-capped at the new
        expiry. A finished or expired bounty is history and can't be edited.
        """
        bounty = self._require_bounty(bounty_id)
        if bounty.status in ("completed", "expired"):
            raise ValueError("A finished bounty can't be edited.")
        fields = self._clean_bounty_fields(changes)
        if bounty.status != "open":
            locked = [k for k, v in fields.items() if k not in _CLAIMED_EDITABLE and getattr(bounty, k) != v]
            if locked:
                raise ValueError("Once a bounty is claimed, only its points and expiry can change.")
        now = dt_util.now()
        if "expires_at" in fields and fields["expires_at"] is not None and fields["expires_at"] <= now:
            if bounty.status == "open" or fields["expires_at"] != bounty.expires_at:
                raise ValueError("The expiry is already in the past.")
        for key, value in fields.items():
            setattr(bounty, key, value)
        if bounty.status == "claimed" and bounty.claimed_at is not None:
            bounty.claim_until = self._bounty_lock_until(bounty, bounty.claimed_at)
        if bounty.status == "pending" and "points" in fields:
            # Approval pays what the submission was worth; the parent just
            # changed that, so the waiting completion follows.
            completion = self._bounty_completion(bounty)
            if completion is not None:
                completion.submitted_points = bounty.points
                self.storage.update_completion(completion)
        self.storage.update_bounty(bounty)
        await self.storage.async_save()
        self.hass.bus.async_fire(
            "taskmate_bounty_updated",
            {
                "bounty_id": bounty.id,
                "title": bounty.title,
                "points": bounty.points,
                "claimed_by": bounty.claimed_by if bounty.status in ("claimed", "pending") else "",
            },
        )
        await self.async_refresh()
        return bounty

    async def async_remove_bounty(self, bounty_id: str) -> None:
        """Take a bounty off the board (or out of the history).

        Refused while a completion waits for approval: approve or reject that
        first, so the child's submission isn't silently thrown away.
        """
        bounty = self._require_bounty(bounty_id)
        if bounty.status == "pending":
            raise ValueError("Approve or reject the finished job before removing this bounty.")
        self.storage.remove_bounty(bounty_id)
        await self.storage.async_save()
        self.hass.bus.async_fire("taskmate_bounty_removed", {"bounty_id": bounty.id, "title": bounty.title})
        await self.async_refresh()

    async def async_release_bounty(self, bounty_id: str) -> None:
        """A parent puts a claimed bounty back on the board."""
        bounty = self._require_bounty(bounty_id)
        if bounty.status != "claimed":
            raise ValueError("Only a claimed bounty can be released.")
        child_id = bounty.claimed_by
        bounty.clear_claim()
        bounty.status = "open"
        self.storage.update_bounty(bounty)
        await self.storage.async_save()
        self._fire_bounty_event("taskmate_bounty_released", bounty, child_id)
        await self.async_refresh()

    # ── child: claim / give back / complete ──────────────────────────────

    async def async_claim_bounty(self, bounty_id: str, child_id: str) -> Bounty:
        """Lock a bounty to ``child_id`` for its claim period."""
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        bounty = self._require_bounty(bounty_id)
        if not bounty.is_eligible(child_id):
            raise ValueError("This bounty isn't for you.")
        now = dt_util.now()
        if bounty.status != "open" or (bounty.expires_at is not None and bounty.expires_at <= now):
            raise ValueError("Someone else got there first — this bounty isn't on the board any more.")
        current = self.active_bounty_claim(child_id)
        if current is not None:
            raise ValueError(f"Finish '{current.title}' first — you can only hold one bounty at a time.")
        bounty.status = "claimed"
        bounty.claimed_by = child_id
        bounty.claimed_at = now
        bounty.claim_until = self._bounty_lock_until(bounty, now)
        bounty.lapse_warned = False
        self.storage.update_bounty(bounty)
        await self.storage.async_save()
        self._fire_bounty_event("taskmate_bounty_claimed", bounty, child_id)
        await self.async_refresh()
        return bounty

    async def async_give_back_bounty(self, bounty_id: str, child_id: str) -> None:
        """The claimer hands a bounty back to the board."""
        bounty = self._require_bounty(bounty_id)
        if bounty.status != "claimed" or bounty.claimed_by != child_id:
            raise ValueError("You don't have this bounty claimed.")
        bounty.clear_claim()
        bounty.status = "open"
        self.storage.update_bounty(bounty)
        await self.storage.async_save()
        self._fire_bounty_event("taskmate_bounty_given_back", bounty, child_id)
        await self.async_refresh()

    async def async_complete_bounty(self, bounty_id: str, child_id: str, photo_url: str = "") -> ChoreCompletion:
        """The claimer says it's done: submit it to the approval queue.

        A bounty always goes to a parent — it's a one-off, priced by hand — so
        the completion is recorded pending, like an approval-required chore.
        """
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        bounty = self._require_bounty(bounty_id)
        if bounty.status != "claimed" or bounty.claimed_by != child_id:
            raise ValueError("You don't have this bounty claimed.")
        now = dt_util.now()
        if bounty.claim_until is not None and bounty.claim_until <= now:
            raise ValueError("Your claim on this bounty ran out.")
        if photo_url and not photos.is_taskmate_photo_url(photo_url):
            _LOGGER.warning("Ignoring invalid photo_url for bounty %s (not a TaskMate photo URL)", bounty_id)
            photo_url = ""
        if bounty.require_photo and not photo_url:
            raise ValueError("This bounty needs a photo of the finished job.")

        completion = ChoreCompletion(
            chore_id=bounty.id,
            bounty_id=bounty.id,
            child_id=child_id,
            completed_at=now,
            approved=False,
            points_awarded=0,
            submitted_points=bounty.points,
            photo_url=photo_url,
            child_undo_allowed=undo_window_seconds(self.storage) > 0,
        )
        self.storage.add_completion(completion)
        bounty.status = "pending"
        bounty.completion_id = completion.id
        self.storage.update_bounty(bounty)
        await self.storage.async_save()
        self.hass.bus.async_fire(
            "taskmate_chore_completed",
            {
                "child_id": child.id,
                "child_name": child.name,
                "chore_id": bounty.id,
                "chore_name": bounty.title,
                "bounty_id": bounty.id,
                "points": bounty.points,
                "timestamp": now.isoformat(),
            },
        )
        self._fire_bounty_event("taskmate_bounty_completed", bounty, child_id)
        await self._async_notify_pending_approval(
            child.name, bounty.title, bounty.points, completion_id=completion.id, photo_url=photo_url
        )
        await self.async_refresh()
        return completion

    # ── hooks from the chore approval paths ──────────────────────────────

    def _bounty_completion(self, bounty: Bounty):
        return next((c for c in self.storage.get_completions() if c.id == bounty.completion_id), None)

    def _bounty_on_approved(self, completion) -> None:
        """A parent approved the bounty's completion: it's done."""
        bounty = self.storage.get_bounty(getattr(completion, "bounty_id", "") or "")
        if bounty is None:
            return
        bounty.status = "completed"
        bounty.claimed_by = completion.child_id
        bounty.completion_id = completion.id
        bounty.points_awarded = int(completion.points_awarded or 0)
        bounty.closed_at = dt_util.now()
        bounty.claim_until = None
        self.storage.update_bounty(bounty)
        self._fire_bounty_event("taskmate_bounty_approved", bounty, completion.child_id)

    def _bounty_on_unapproved(self, completion) -> None:
        """A parent undid the approval: the completion is back in the queue."""
        bounty = self.storage.get_bounty(getattr(completion, "bounty_id", "") or "")
        if bounty is None:
            return
        bounty.status = "pending"
        bounty.claimed_by = completion.child_id
        bounty.completion_id = completion.id
        bounty.points_awarded = 0
        bounty.closed_at = None
        self.storage.update_bounty(bounty)

    def _bounty_on_withdrawn(self, completion, *, rejected: bool) -> None:
        """The completion was rejected (or the child took it back): the job
        goes back to the same child, not to the board.

        A rejection renews the lock in full — they have work to redo, and that
        holds even past the bounty's expiry. A child's own undo keeps the lock
        they already had; if it has run out, the next sweep lapses it.
        """
        bounty = self.storage.get_bounty(getattr(completion, "bounty_id", "") or "")
        if bounty is None or bounty.completion_id != completion.id:
            return
        if not self.get_child(completion.child_id):
            bounty.clear_claim()
            bounty.status = "open"
        else:
            now = dt_util.now()
            bounty.status = "claimed"
            bounty.claimed_by = completion.child_id
            bounty.completion_id = ""
            bounty.points_awarded = 0
            bounty.closed_at = None
            if rejected or bounty.claim_until is None:
                bounty.claimed_at = now
                bounty.claim_until = self._bounty_lock_until(bounty, now, cap_at_expiry=False)
                bounty.lapse_warned = False
        self.storage.update_bounty(bounty)
        self._fire_bounty_event(
            "taskmate_bounty_rejected" if rejected else "taskmate_bounty_withdrawn", bounty, completion.child_id
        )

    # ── housekeeping ─────────────────────────────────────────────────────

    async def async_sweep_bounties(self, refresh: bool = True) -> bool:
        """Lapse run-out claims, expire unclaimed bounties, warn claimers.

        Runs on the coordinator's update tick and at startup. ``refresh=False``
        when called from inside the refresh itself. Returns whether anything
        changed.
        """
        bounties = self.storage.get_bounties()
        if not bounties:
            return False
        now = dt_util.now()
        warn_window = timedelta(minutes=BOUNTY_LAPSE_WARNING_MINUTES)
        changed = False
        events: list[tuple[str, Bounty, str]] = []
        warnings: list[tuple[Bounty, str]] = []
        for bounty in bounties:
            if bounty.status == "claimed" and bounty.claim_until is not None:
                child_id = bounty.claimed_by
                if bounty.claim_until <= now:
                    bounty.clear_claim()
                    bounty.lapse_count += 1
                    expired = bounty.expires_at is not None and bounty.expires_at <= now
                    bounty.status = "expired" if expired else "open"
                    if expired:
                        bounty.closed_at = now
                    events.append(("taskmate_bounty_claim_lapsed", bounty, child_id))
                    self.storage.update_bounty(bounty)
                    changed = True
                elif (
                    not bounty.lapse_warned
                    and bounty.claim_until - now <= warn_window
                    # A lock that was never longer than the warning window
                    # (the expiry cut it short) would warn the moment it was
                    # claimed — which tells the child nothing.
                    and (bounty.claimed_at is None or bounty.claim_until - bounty.claimed_at > warn_window)
                ):
                    bounty.lapse_warned = True
                    warnings.append((bounty, child_id))
                    self.storage.update_bounty(bounty)
                    changed = True
            elif bounty.status == "open" and bounty.expires_at is not None and bounty.expires_at <= now:
                bounty.status = "expired"
                bounty.closed_at = now
                events.append(("taskmate_bounty_expired", bounty, ""))
                self.storage.update_bounty(bounty)
                changed = True
        if not changed:
            return False
        await self.storage.async_save()
        for event, bounty, child_id in events:
            self._fire_bounty_event(event, bounty, child_id)
        for bounty, child_id in warnings:
            child = self.get_child(child_id)
            if child is None:
                continue
            minutes = max(1, round((bounty.claim_until - now).total_seconds() / 60))
            await self.notifications.fire(
                "bounty_claim_lapsing",
                {
                    "child_name": child.name,
                    "child_id": child.id,
                    "bounty_name": bounty.title,
                    "minutes": minutes,
                },
                only_recipients={f"child:{child.id}"},
            )
        if refresh:
            await self.async_refresh()
        return True

    async def async_prune_bounties(self) -> None:
        """Drop finished bounties older than the completion history (midnight).

        Kept exactly as long as the completions they explain, so the activity
        feed never shows a bounty completion with no name.
        """
        try:
            days = int(self.storage.get_setting("history_days", "90"))
        except (TypeError, ValueError):
            days = 90
        cutoff = dt_util.now() - timedelta(days=days)
        stale = [
            b.id
            for b in self.storage.get_bounties()
            if b.status in ("completed", "expired") and b.closed_at is not None and b.closed_at < cutoff
        ]
        if not stale:
            return
        for bounty_id in stale:
            self.storage.remove_bounty(bounty_id)
        await self.storage.async_save()

    def remove_child_from_bounties(self, child_id: str) -> None:
        """Follow a deleted child: free their claim, drop them from eligibility.

        A bounty that was only for them has nobody left to do it, so it goes
        (unless it's history). Their completions are removed separately, which
        is why a pending bounty of theirs goes back on the board.
        """
        for bounty in self.storage.get_bounties():
            dirty = False
            if bounty.status in ("claimed", "pending") and bounty.claimed_by == child_id:
                bounty.clear_claim()
                bounty.status = "open"
                dirty = True
            if child_id in bounty.eligible_child_ids:
                bounty.eligible_child_ids = [c for c in bounty.eligible_child_ids if c != child_id]
                if not bounty.eligible_child_ids and bounty.status == "open":
                    self.storage.remove_bounty(bounty.id)
                    continue
                dirty = True
            if dirty:
                self.storage.update_bounty(bounty)

    def _fire_bounty_event(self, event: str, bounty: Bounty, child_id: str) -> None:
        child = self.get_child(child_id) if child_id else None
        self.hass.bus.async_fire(
            event,
            {
                "bounty_id": bounty.id,
                "title": bounty.title,
                "points": bounty.points,
                "child_id": child_id,
                "child_name": getattr(child, "name", ""),
                "timestamp": dt_util.now().isoformat(),
            },
        )
