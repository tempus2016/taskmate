"""Make it right: earn a penalty back by doing a chore.

A penalty can name a "make it right" chore. When it is applied, the child gets
an offer: do that chore within N days (end of the day N-1 days after the
penalty) and get some or all of the deducted points back. Losing points
teaches less than repairing the thing that went wrong.

While an offer is open the chore is available to that child even on a day it
isn't normally scheduled, so "tidy the mess you made" can be done straight
away. The refund is paid when the completion is approved (or straight away
when the chore needs no approval), and taken back again if that completion is
undone or rejected.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import NOTIF_TYPE_PENALTY_REDEEMED
from .models import PointsTransaction, generate_id, parse_datetime

REDEMPTIONS_KEEP = 200


class RedemptionsMixin:
    """Penalty make-it-right offers."""

    def _redemptions(self) -> list[dict[str, Any]]:
        return self.storage.get_section("penalty_redemptions", list)

    @staticmethod
    def _offer_open(offer: dict[str, Any], today: date) -> bool:
        if offer.get("status") != "open":
            return False
        try:
            return today <= date.fromisoformat(offer.get("expires", ""))
        except (TypeError, ValueError):
            return False

    def open_redemptions(self, child_id: str) -> list[dict[str, Any]]:
        today = dt_util.as_local(dt_util.now()).date()
        return [o for o in self._redemptions() if o.get("child_id") == child_id and self._offer_open(o, today)]

    def open_redemption_for(self, chore_id: str, child_id: str) -> dict[str, Any] | None:
        for offer in self.open_redemptions(child_id):
            if offer.get("chore_id") == chore_id:
                return offer
        return None

    def _create_redemption_offer(self, penalty, child, deducted: int) -> dict[str, Any] | None:
        chore_id = getattr(penalty, "redemption_chore_id", "") or ""
        chore = self.get_chore(chore_id) if chore_id else None
        if chore is None or deducted <= 0:
            return None
        percent = max(1, min(100, int(getattr(penalty, "redemption_percent", 100) or 100)))
        days = max(1, min(7, int(getattr(penalty, "redemption_days", 1) or 1)))
        refund = max(1, round(deducted * percent / 100))
        today = dt_util.as_local(dt_util.now()).date()
        offer = {
            "id": generate_id(),
            "child_id": child.id,
            "penalty_id": penalty.id,
            "penalty_name": penalty.name,
            "chore_id": chore.id,
            "chore_name": chore.name,
            "points": refund,
            "created_at": dt_util.now().isoformat(),
            "expires": (today + timedelta(days=days - 1)).isoformat(),
            "status": "open",
        }
        offers = self._redemptions()
        offers.append(offer)
        del offers[:-REDEMPTIONS_KEEP]
        return offer

    async def _async_redeem_penalty(self, chore, child, completion) -> None:
        """Pay an open offer the approved ``completion`` fulfils."""
        if completion.bonus_subtask_id or not child:
            return
        offer = self.open_redemption_for(chore.id, child.id)
        if offer is None:
            return
        # Compare instants, not strings: the offer is stamped in local time and
        # completions in UTC, so "22:30+00:00" < "23:10+01:00" as text even
        # though it is later.
        created = parse_datetime(offer.get("created_at"))
        done_at = getattr(completion, "completed_at", None)
        if created is None or done_at is None or done_at < created:
            return
        refund = int(offer.get("points", 0) or 0)
        offer["status"] = "redeemed"
        offer["completion_id"] = completion.id
        offer["redeemed_at"] = dt_util.now().isoformat()
        child.points += refund
        child.total_penalties_received = max(0, (child.total_penalties_received or 0) - refund)
        child.career_score = child.total_points_earned - child.total_penalties_received
        self.storage.update_child(child)
        self.storage.add_points_transaction(
            PointsTransaction(
                child_id=child.id,
                points=refund,
                reason=f"Made it right: {offer.get('penalty_name', '')}",
                created_at=dt_util.now(),
            )
        )
        await self.storage.async_save()
        await self.notifications.fire(
            NOTIF_TYPE_PENALTY_REDEEMED,
            {
                "child_id": child.id,
                "child_name": child.name,
                "penalty_name": offer.get("penalty_name", ""),
                "chore_name": chore.name,
                "points": refund,
                "points_name": self.storage.get_points_name(),
            },
        )

    def _reverse_penalty_redemption(self, completion, child) -> None:
        """Undoing or rejecting the completion that earned a penalty back takes the refund back."""
        if not child:
            return
        for offer in self._redemptions():
            if offer.get("status") == "redeemed" and offer.get("completion_id") == completion.id:
                refund = int(offer.get("points", 0) or 0)
                offer["status"] = "open"
                offer.pop("completion_id", None)
                offer.pop("redeemed_at", None)
                child.points = (
                    child.points - refund
                    if self._setting_enabled("allow_negative_balance")
                    else max(0, child.points - refund)
                )
                child.total_penalties_received = (child.total_penalties_received or 0) + refund
                child.career_score = child.total_points_earned - child.total_penalties_received
                self.storage.add_points_transaction(
                    PointsTransaction(
                        child_id=child.id,
                        points=-refund,
                        reason=f"Made it right undone: {offer.get('penalty_name', '')}",
                        created_at=dt_util.now(),
                    )
                )
                return
