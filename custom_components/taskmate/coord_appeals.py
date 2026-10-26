"""Appeals: a child can ask for a second look at a rejection or a penalty.

With ``appeals_enabled`` on, a child's card lists what they may appeal: a
chore or reward claim a parent rejected, or a penalty applied to them, from
the last ``APPEAL_WINDOW_HOURS`` hours. One appeal per item, with an optional
message. The parents get a push (``appeal_submitted``, on by default like a
help request) and the appeal waits on the panel's Today page.

Deciding it:
  * **Uphold** — nothing changes; the child sees the parent's note.
  * **Overturn** — a rejected chore pays its points, a rejected reward claim
    is approved there and then, a penalty is undone (and any open make-it-right
    offer for it is closed).

A penalty the child has already earned back with its make-it-right chore
can't be appealed: it has been put right already. Wishlist redemptions keep
their own decline flow and are never appealable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from . import notify_strings
from .const import NOTIF_TYPE_APPEAL_DECIDED, NOTIF_TYPE_APPEAL_SUBMITTED
from .models import RewardClaim, clean_label, generate_id, parse_datetime

_LOGGER = logging.getLogger(__name__)

APPEAL_WINDOW_HOURS = 48
APPEAL_MESSAGE_MAX = 200
APPEAL_NOTE_MAX = 200
APPEAL_KINDS = ("chore", "reward", "penalty")
# Decided appeals stay on the child's card this long.
APPEAL_SHOW_DECIDED_HOURS = 24
APPEAL_KEEP = 100
# How close a make-it-right offer's creation must be to the penalty's
# transaction to count as that penalty's offer.
_OFFER_MATCH = timedelta(minutes=2)
_PENALTY_PREFIX = "Penalty: "


def _when(value) -> datetime | None:
    try:
        return parse_datetime(value)
    except (TypeError, ValueError):
        return None


class AppealsMixin:
    """Children appeal rejections and penalties; parents uphold or overturn."""

    def appeals_enabled(self) -> bool:
        v = self.storage.get_setting("appeals_enabled", False)
        return v is True or str(v).lower() == "true"

    def _appeals(self) -> list[dict[str, Any]]:
        return self.storage.get_section("appeals", list)

    def _appealed_targets(self) -> set[str]:
        return {a.get("target_id") for a in self._appeals()}

    def _penalty_offer(self, child_id: str, name: str, at: datetime) -> dict[str, Any] | None:
        """The make-it-right offer that penalty transaction created, if any."""
        for offer in self.storage.get_section("penalty_redemptions", list):
            if offer.get("child_id") != child_id or offer.get("penalty_name") != name:
                continue
            created = _when(offer.get("created_at"))
            if created is not None and abs(created - at) <= _OFFER_MATCH:
                return offer
        return None

    def appealable_for_child(self, child_id: str) -> list[dict[str, Any]]:
        """What this child may still appeal, newest first."""
        if not self.appeals_enabled():
            return []
        now = dt_util.now()
        cutoff = now - timedelta(hours=APPEAL_WINDOW_HOURS)
        taken = self._appealed_targets()
        out: list[dict[str, Any]] = []
        for row in self.storage.get_rejections():
            if row.get("child_id") != child_id or row.get("wish") or row.get("kind") not in ("chore", "reward"):
                continue
            at = _when(row.get("rejected_at"))
            if at is None or at < cutoff or row.get("id") in taken:
                continue
            out.append(
                {
                    "kind": row["kind"],
                    "target_id": row["id"],
                    "item_id": row.get("item_id", ""),
                    "name": row.get("item_name", ""),
                    "points": int(row.get("points", 0) or 0),
                    "at": at.isoformat(),
                }
            )
        for txn in self.storage.get_points_transactions():
            if txn.child_id != child_id or not (txn.reason or "").startswith(_PENALTY_PREFIX) or txn.points >= 0:
                continue
            if txn.created_at < cutoff or txn.id in taken:
                continue
            name = txn.reason[len(_PENALTY_PREFIX) :]
            offer = self._penalty_offer(child_id, name, txn.created_at)
            if offer is not None and offer.get("status") == "redeemed":
                continue
            out.append(
                {
                    "kind": "penalty",
                    "target_id": txn.id,
                    "item_id": "",
                    "name": name,
                    "points": -txn.points,
                    "at": txn.created_at.isoformat(),
                }
            )
        out.sort(key=lambda i: i["at"], reverse=True)
        return out[:5]

    async def async_appeal(self, child_id: str, kind: str, target_id: str, message: str = "") -> dict[str, Any]:
        """A child appeals one item from their appealable list."""
        if not self.appeals_enabled():
            raise ValueError("Appeals are switched off.")
        child = self.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        if target_id in self._appealed_targets():
            raise ValueError("That has already been appealed.")
        item = next(
            (i for i in self.appealable_for_child(child_id) if i["kind"] == kind and i["target_id"] == target_id), None
        )
        if item is None:
            raise ValueError("That can't be appealed.")
        now = dt_util.now()
        record = {
            "id": generate_id(),
            "child_id": child_id,
            "kind": kind,
            "target_id": target_id,
            "item_id": item["item_id"],
            "item_name": item["name"],
            "points": item["points"],
            "message": clean_label(message, APPEAL_MESSAGE_MAX),
            "status": "open",
            "created_at": now.isoformat(),
        }
        appeals = self._appeals()
        appeals.append(record)
        _trim(appeals)
        await self.storage.async_save()
        payload = {
            "appeal_id": record["id"],
            "child_id": child_id,
            "child_name": child.name,
            "kind": kind,
            "item_name": record["item_name"],
            "points": record["points"],
            "message": record["message"],
        }
        self.hass.bus.async_fire("taskmate_appeal_submitted", {**payload, "timestamp": now.isoformat()})
        if getattr(self, "notifications", None):
            await self.notifications.fire(
                NOTIF_TYPE_APPEAL_SUBMITTED,
                {**payload, "message_text": f" — “{record['message']}”" if record["message"] else ""},
            )
        await self.async_refresh()
        return dict(record)

    def open_appeals(self) -> list[dict[str, Any]]:
        """Appeals waiting for a parent, oldest first, with the child's name."""
        names = {c.id: c.name for c in self.storage.get_children()}
        return [
            {**a, "child_name": names.get(a.get("child_id"), "")} for a in self._appeals() if a.get("status") == "open"
        ]

    def appeals_for_child(self, child_id: str) -> list[dict[str, Any]]:
        """This child's open appeals and the ones decided in the last day, compact, newest first."""
        cutoff = dt_util.now() - timedelta(hours=APPEAL_SHOW_DECIDED_HOURS)
        out = []
        for a in reversed(self._appeals()):
            if a.get("child_id") != child_id:
                continue
            if a.get("status") != "open":
                decided = _when(a.get("decided_at"))
                if decided is None or decided < cutoff:
                    continue
            row = {k: a[k] for k in ("id", "kind", "item_name", "points", "status") if k in a}
            if a.get("note"):
                row["note"] = a["note"]
            out.append(row)
        return out[:5]

    async def async_decide_appeal(self, appeal_id: str, overturn: bool, note: str = "") -> dict[str, Any]:
        """A parent upholds the original decision or overturns it."""
        appeal = next((a for a in self._appeals() if a.get("id") == appeal_id), None)
        if appeal is None:
            raise ValueError("That appeal no longer exists.")
        if appeal.get("status") != "open":
            raise ValueError("That appeal has already been decided.")
        child = self.get_child(appeal["child_id"])
        if child is None:
            raise ValueError("The child is no longer here.")
        if overturn:
            await self._async_overturn(appeal, child)
        now = dt_util.now()
        appeal["status"] = "overturned" if overturn else "upheld"
        appeal["decided_at"] = now.isoformat()
        appeal["note"] = clean_label(note, APPEAL_NOTE_MAX)
        await self.storage.async_save()
        payload = {
            "appeal_id": appeal["id"],
            "child_id": child.id,
            "child_name": child.name,
            "kind": appeal["kind"],
            "item_name": appeal["item_name"],
            "points": appeal["points"],
            "overturned": bool(overturn),
            "note": appeal["note"],
        }
        self.hass.bus.async_fire("taskmate_appeal_decided", {**payload, "timestamp": now.isoformat()})
        if getattr(self, "notifications", None):
            await self.notifications.fire(
                NOTIF_TYPE_APPEAL_DECIDED,
                {
                    **payload,
                    "outcome": notify_strings.text(
                        self.hass, "appeal_outcome_overturned" if overturn else "appeal_outcome_upheld"
                    ),
                    "note_text": f": {appeal['note']}" if appeal["note"] else "",
                },
                only_recipients={f"child:{child.id}"},
            )
        await self.async_refresh()
        return dict(appeal)

    async def _async_overturn(self, appeal: dict[str, Any], child) -> None:
        kind = appeal["kind"]
        if kind == "chore":
            points = int(appeal.get("points", 0) or 0)
            if points > 0:
                await self.async_add_points(child.id, points, reason=f"Appeal: {appeal['item_name']}")
            return
        if kind == "reward":
            reward = self.get_reward(appeal.get("item_id", ""))
            if reward is None:
                raise ValueError("That reward no longer exists.")
            claim = RewardClaim(reward_id=reward.id, child_id=child.id, claimed_at=dt_util.now())
            self.storage.add_reward_claim(claim)
            try:
                await self.async_approve_reward(claim.id)
            except ValueError:
                self.storage.remove_reward_claim(claim.id)
                raise
            return
        if kind == "penalty":
            txn = next((t for t in self.storage.get_points_transactions() if t.id == appeal["target_id"]), None)
            if txn is None:
                raise ValueError("That penalty has already been taken back.")
            # The undo settles the make-it-right offer: cancels an open one,
            # refuses when the penalty was already earned back.
            await self.async_undo_transaction(txn.id)
            return
        raise ValueError(f"Unknown appeal kind {kind}")


def _trim(appeals: list[dict[str, Any]]) -> None:
    """Keep every open appeal and the newest decided ones."""
    decided = [a for a in appeals if a.get("status") != "open"]
    extra = len(decided) - APPEAL_KEEP
    if extra > 0:
        drop = {id(a) for a in decided[:extra]}
        appeals[:] = [a for a in appeals if id(a) not in drop]
