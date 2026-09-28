"""Wishlist with pledges (#932) — mixin for TaskMateCoordinator.

A child adds something they want with a suggested price; a parent approves
it (confirming or changing the target) and it becomes a savings goal. The
child moves points into it, and a parent records pledges from relatives
("Grandma +20"). Once saved + pledged reach the target the child asks to
redeem, which turns the wish into an ordinary pending reward claim for the
parent to approve.

Accounting mirrors the savings jars in coord_rewards.py: points a child moves
in leave ``Child.points`` immediately (so they can't be spent twice) and are
held on the wish as ``saved``. Pledged points are a gift attached to the wish
and never touch any balance, so the only thing they can ever turn into is the
wish itself. Every movement writes a PointsTransaction — zero-point rows for
the pledges and the redemption — so the activity log explains each change.
Those rows are on the undo deny-list: the matching operation here (take
points back, remove a pledge) is the undo, and reversing a row on its own
would desync the wish from the balance.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

from . import images, photos
from .const import (
    WISH_KEEP_DECLINED_PER_CHILD,
    WISH_KEEP_REDEEMED_PER_CHILD,
    WISH_MAX_OPEN_PER_CHILD,
    WISH_MAX_PLEDGES,
    WISH_MAX_TARGET,
)
from .models import (
    PLEDGE_MESSAGE_MAX,
    PLEDGE_NAME_MAX,
    WISH_DECLINE_REASON_MAX,
    WISH_NAME_MAX,
    PointsTransaction,
    RewardClaim,
    Wish,
    WishPledge,
    clean_label,
    clean_wish_link,
)

if TYPE_CHECKING:
    from .models import Child

_LOGGER = logging.getLogger(__name__)

# Statuses that hold a slot against the per-child limit.
OPEN_STATUSES = ("pending", "active", "redeem_requested")

# Pledge chips carried per wish on the sensor; the panel has the full list.
_SENSOR_PLEDGERS = 6


class WishlistMixin:
    """Mixin providing the wishlist: wishes, savings, pledges and redemption."""

    # ── lookups ──────────────────────────────────────────────────────────
    def get_wish(self, wish_id: str) -> Wish | None:
        return self.storage.get_wish(wish_id)

    def _require_wish(self, wish_id: str, child_id: str | None = None) -> Wish:
        """Return the wish, or raise if it doesn't exist or isn't this child's."""
        wish = self.storage.get_wish(wish_id)
        if wish is None or (child_id is not None and wish.child_id != child_id):
            raise ValueError("Wish not found")
        return wish

    def _require_child(self, child_id: str) -> Child:
        child = self.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        return child

    @staticmethod
    def is_wish_claim(claim: RewardClaim) -> bool:
        return bool(getattr(claim, "wish_id", ""))

    def _wish_spendable(self, child: Child) -> int:
        """Balance a child can still move: points not promised to a pending claim.

        Same rule as allocating to a savings jar — a claim waiting for approval
        is paid from the wallet on approval, so its cost is already spoken for.
        """
        committed = 0
        for claim in self.storage.get_pending_reward_claims():
            if claim.child_id != child.id or self.is_pool_mode_claim(claim):
                continue
            reward = self.get_reward(claim.reward_id)
            if reward:
                committed += reward.cost
        return max(0, child.points - committed)

    def _wish_log(self, child_id: str, points: int, reason: str, *, count_for_season: bool = True) -> None:
        self.storage.add_points_transaction(
            PointsTransaction(child_id=child_id, points=points, reason=reason, created_at=dt_util.now()),
            count_for_season=count_for_season,
        )

    @staticmethod
    def _valid_target(target) -> int:
        try:
            value = int(target)
        except (TypeError, ValueError) as err:
            raise ValueError("The target must be a whole number") from err
        if value < 1 or value > WISH_MAX_TARGET:
            raise ValueError(f"The target must be between 1 and {WISH_MAX_TARGET}")
        return value

    # ── child actions ────────────────────────────────────────────────────
    async def async_add_wish(
        self,
        child_id: str,
        name: str,
        target: int,
        link: str = "",
        photo_url: str = "",
    ) -> Wish:
        """A child asks for something. It waits for a parent before saving can start."""
        child = self._require_child(child_id)
        clean_name = clean_label(name, WISH_NAME_MAX)
        if not clean_name:
            raise ValueError("Give the wish a name")
        value = self._valid_target(target)
        clean_link = clean_wish_link(link)
        if (link or "").strip() and not clean_link:
            raise ValueError("Links must be a web address starting with http:// or https://")
        open_count = sum(1 for w in self.storage.get_wishes() if w.child_id == child_id and w.status in OPEN_STATUSES)
        if open_count >= WISH_MAX_OPEN_PER_CHILD:
            raise ValueError(f"{child.name} already has {WISH_MAX_OPEN_PER_CHILD} wishes on the go")

        image_url = ""
        if photo_url:
            image_url = await self._async_adopt_wish_photo(photo_url)

        wish = Wish(child_id=child_id, name=clean_name, target=value, suggested_target=value, link=clean_link)
        wish.image_url = image_url
        self.storage.upsert_wish(wish)
        await self.storage.async_save()
        await self.async_refresh()

        self._fire_wish_event("taskmate_wish_added", wish, child)
        if getattr(self, "notifications", None):
            await self.notifications.fire(
                "wish_requested",
                {
                    "child_name": child.name,
                    "child_id": child.id,
                    "wish_name": wish.name,
                    "target": wish.target,
                    "points_name": self.storage.get_points_name(),
                },
            )
        return wish

    async def _async_adopt_wish_photo(self, photo_url: str) -> str:
        """Take over a picture the card just uploaded, or refuse it.

        A photo already attached to a chore completion is somebody's evidence
        — readable only by parents and that child — and must not be copied
        somewhere every signed-in user can see it.
        """
        if not photos.is_taskmate_photo_url(photo_url):
            raise ValueError("That picture can't be used")
        if any(getattr(c, "photo_url", "") == photo_url for c in self.storage.get_completions()):
            raise ValueError("That picture can't be used")
        image_url = await images.async_adopt_photo(self.hass, photo_url)
        if not image_url:
            raise ValueError("That picture can't be used")
        return image_url

    async def async_withdraw_wish(self, wish_id: str, child_id: str) -> None:
        """A child takes back a wish still waiting for approval, or clears a declined one."""
        wish = self._require_wish(wish_id, child_id)
        if wish.status not in ("pending", "declined"):
            raise ValueError("Only a wish that is waiting or was declined can be withdrawn")
        self.storage.remove_wish(wish.id)
        await self.storage.async_save()
        await self.async_refresh()
        await self._async_release_wish_image(wish)

    async def async_move_points_to_wish(self, wish_id: str, child_id: str, points: int) -> int:
        """Move points from the child's balance into a wish. Returns what was moved.

        Capped silently at the spendable balance and at what the wish still
        needs, like allocating to a savings jar.
        """
        wish = self._require_wish(wish_id, child_id)
        child = self._require_child(child_id)
        if wish.status != "active":
            raise ValueError(f"'{wish.name}' isn't open for saving")
        if int(points) < 1:
            raise ValueError("Points to move must be at least 1")
        room = wish.remaining
        if room <= 0:
            raise ValueError(f"'{wish.name}' is already fully funded")
        spendable = self._wish_spendable(child)
        if spendable < 1:
            raise ValueError(f"No spendable points available for {child.name}")
        moved = min(int(points), spendable, room)

        child.points -= moved
        self.storage.update_child(child)
        wish.saved += moved
        self.storage.upsert_wish(wish)
        self._wish_log(child.id, -moved, f"Wish savings: {wish.name}")
        await self.storage.async_save()
        await self.async_refresh()
        self._fire_wish_event("taskmate_wish_saved", wish, child, points=moved)
        return moved

    async def async_take_points_from_wish(self, wish_id: str, child_id: str, points: int) -> int:
        """Give some of the child's own savings back. Pledges never come out."""
        wish = self._require_wish(wish_id, child_id)
        child = self._require_child(child_id)
        if wish.status != "active":
            raise ValueError(f"Points can't be taken out of '{wish.name}' right now")
        if int(points) < 1:
            raise ValueError("Points to take back must be at least 1")
        if wish.saved <= 0:
            raise ValueError(f"Nothing saved in '{wish.name}' to take back")
        taken = min(int(points), wish.saved)

        child.points += taken
        self.storage.update_child(child)
        wish.saved -= taken
        self.storage.upsert_wish(wish)
        # The child's own points coming home, not new ones: keep it off the
        # leaderboard, or moving points in and out would farm season points.
        self._wish_log(child.id, taken, f"Wish savings taken back: {wish.name}", count_for_season=False)
        await self.storage.async_save()
        await self.async_refresh()
        return taken

    async def async_request_wish_redeem(self, wish_id: str, child_id: str) -> RewardClaim:
        """A funded wish becomes an ordinary pending reward claim for the parent."""
        from .coord_rewards import _MAX_PENDING_CLAIMS_PER_CHILD

        wish = self._require_wish(wish_id, child_id)
        child = self._require_child(child_id)
        if wish.status != "active":
            raise ValueError(f"'{wish.name}' can't be redeemed right now")
        if not wish.funded:
            raise ValueError(f"'{wish.name}' needs {wish.remaining} more points first")
        own_pending = [c for c in self.storage.get_pending_reward_claims() if c.child_id == child_id]
        if len(own_pending) >= _MAX_PENDING_CLAIMS_PER_CHILD:
            raise ValueError("Too many reward claims are already waiting for approval")

        claim = RewardClaim(reward_id=wish.id, child_id=child_id, claimed_at=dt_util.now(), wish_id=wish.id)
        self.storage.add_reward_claim(claim)
        wish.status = "redeem_requested"
        wish.claim_id = claim.id
        self.storage.upsert_wish(wish)
        await self.storage.async_save()
        await self.async_refresh()

        self.hass.bus.async_fire(
            "taskmate_reward_claimed",
            {
                "child_id": child.id,
                "reward_id": wish.id,
                "wish_id": wish.id,
                "claim_id": claim.id,
                "cost": wish.target,
                "timestamp": dt_util.now().isoformat(),
            },
        )
        if getattr(self, "notifications", None):
            await self._async_notify_pending_reward_claim(child.name, wish.name, wish.target, claim_id=claim.id)
        return claim

    # ── parent actions ───────────────────────────────────────────────────
    async def async_approve_wish(self, wish_id: str, target: int | None = None) -> Wish:
        """Turn a waiting wish into a savings goal, optionally at a different target."""
        wish = self._require_wish(wish_id)
        if wish.status != "pending":
            raise ValueError(f"'{wish.name}' isn't waiting for approval")
        if target is not None:
            wish.target = self._valid_target(target)
        wish.status = "active"
        wish.approved_at = dt_util.now()
        self.storage.upsert_wish(wish)
        await self.storage.async_save()
        await self.async_refresh()
        self._fire_wish_event("taskmate_wish_approved", wish, self.get_child(wish.child_id))
        return wish

    async def async_decline_wish(self, wish_id: str, reason: str = "") -> None:
        """Say no, with an optional reason the child sees on their card.

        Anything already saved goes back to the child and every pledge is
        voided — pledged points were never the child's.
        """
        wish = self._require_wish(wish_id)
        if wish.status not in OPEN_STATUSES:
            raise ValueError(f"'{wish.name}' can no longer be declined")
        cancelled = self._release_wish(wish, "declined")
        wish.status = "declined"
        wish.declined_at = dt_util.now()
        wish.decline_reason = clean_label(reason, WISH_DECLINE_REASON_MAX)
        self.storage.upsert_wish(wish)
        pruned = self._prune_finished_wishes(wish.child_id, "declined", WISH_KEEP_DECLINED_PER_CHILD)
        await self.storage.async_save()
        await self.async_refresh()
        await self._async_after_release(cancelled, pruned)
        self._fire_wish_event("taskmate_wish_declined", wish, self.get_child(wish.child_id))

    async def async_remove_wish(self, wish_id: str) -> None:
        """Delete a wish outright. Savings go back to the child, pledges are voided."""
        wish = self._require_wish(wish_id)
        cancelled = self._release_wish(wish, "removed") if wish.status in OPEN_STATUSES else []
        self.storage.remove_wish(wish.id)
        await self.storage.async_save()
        await self.async_refresh()
        await self._async_after_release(cancelled, [wish])

    async def async_pledge_to_wish(self, wish_id: str, name: str, points: int, message: str = "") -> WishPledge:
        """Record a relative's gift towards a wish, capped at what it still needs."""
        wish = self._require_wish(wish_id)
        if wish.status != "active":
            raise ValueError(f"'{wish.name}' isn't open for pledges")
        who = clean_label(name, PLEDGE_NAME_MAX)
        if not who:
            raise ValueError("Say who the pledge is from")
        if int(points) < 1:
            raise ValueError("A pledge must be at least 1 point")
        room = wish.remaining
        if room <= 0:
            raise ValueError(f"'{wish.name}' is already fully funded")
        if len(wish.pledges) >= WISH_MAX_PLEDGES:
            raise ValueError(f"'{wish.name}' already has {WISH_MAX_PLEDGES} pledges")
        pledge = WishPledge(
            name=who,
            points=min(int(points), room),
            message=clean_label(message, PLEDGE_MESSAGE_MAX),
            created_at=dt_util.now(),
        )
        wish.pledges.append(pledge)
        self.storage.upsert_wish(wish)
        self._wish_log(wish.child_id, 0, f"Wish pledge from {who} (+{pledge.points}): {wish.name}")
        await self.storage.async_save()
        await self.async_refresh()

        child = self.get_child(wish.child_id)
        self._fire_wish_event("taskmate_wish_pledged", wish, child, points=pledge.points, pledger=who)
        if child and getattr(self, "notifications", None):
            await self.notifications.fire(
                "wish_pledged",
                {
                    "child_name": child.name,
                    "child_id": child.id,
                    "pledger": who,
                    "points": pledge.points,
                    "wish_name": wish.name,
                    "message": pledge.message,
                    "points_name": self.storage.get_points_name(),
                },
                only_recipients={f"child:{child.id}"},
            )
        return pledge

    async def async_remove_wish_pledge(self, wish_id: str, pledge_id: str) -> None:
        """Undo a pledge. Allowed until the wish is redeemed.

        If the wish was waiting to be redeemed and no longer reaches its
        target, the waiting claim is withdrawn and it goes back to saving.
        """
        wish = self._require_wish(wish_id)
        if wish.status not in ("active", "redeem_requested"):
            raise ValueError(f"Pledges on '{wish.name}' can no longer be changed")
        pledge = next((p for p in wish.pledges if p.id == pledge_id), None)
        if pledge is None:
            raise ValueError("Pledge not found")
        wish.pledges = [p for p in wish.pledges if p.id != pledge_id]
        cancelled: list[str] = []
        if wish.status == "redeem_requested" and not wish.funded:
            cancelled = self._cancel_wish_claim(wish)
            wish.status = "active"
        self.storage.upsert_wish(wish)
        self._wish_log(wish.child_id, 0, f"Wish pledge removed ({pledge.name}, {pledge.points}): {wish.name}")
        await self.storage.async_save()
        await self.async_refresh()
        await self._async_after_release(cancelled, [])

    # ── the reward claim a funded wish becomes ───────────────────────────
    async def _async_approve_wish_claim(self, claim: RewardClaim) -> None:
        """Parent approves the redemption: the wish is spent.

        The child's saved points already left their balance when they were
        moved in, so nothing is deducted here. The claim records the child's
        own share as what the purchase cost them; the pledges were gifts.
        """
        wish = self.storage.get_wish(claim.wish_id)
        child = self.get_child(claim.child_id)
        if wish is None or child is None:
            raise ValueError(f"Wish or child not found for claim {claim.id}")
        if wish.status != "redeem_requested" or wish.claim_id != claim.id:
            raise ValueError(f"'{wish.name}' is no longer waiting to be redeemed")
        if not wish.funded:
            raise ValueError(f"'{wish.name}' is not fully funded any more")

        now = dt_util.now()
        wish.status = "redeemed"
        wish.redeemed_at = now
        self.storage.upsert_wish(wish)
        claim.approved = True
        claim.approved_at = now
        claim.approved_cost = wish.saved
        self.storage.update_reward_claim(claim)
        self._wish_log(child.id, 0, f"Wish redeemed: {wish.name}")
        pruned = self._prune_finished_wishes(child.id, "redeemed", WISH_KEEP_REDEEMED_PER_CHILD)
        await self.storage.async_save()
        await self.async_refresh()
        await self._async_after_release([claim.id], pruned)

        self.hass.bus.async_fire(
            "taskmate_reward_approved",
            {
                "child_id": child.id,
                "child_name": child.name,
                "reward_id": wish.id,
                "reward_name": wish.name,
                "wish_id": wish.id,
                "claim_id": claim.id,
                "cost": wish.saved,
                "timestamp": now.isoformat(),
            },
        )
        if getattr(self, "badges", None):
            await self.badges.evaluate_for_child(child.id, "reward_redeemed")

    async def _async_reject_wish_claim(self, claim: RewardClaim, reason: str = "") -> None:
        """Parent says "not yet": the claim goes, the wish keeps its savings."""
        self.storage.remove_reward_claim(claim.id)
        wish = self.storage.get_wish(claim.wish_id)
        if wish is not None and wish.status == "redeem_requested":
            wish.status = "active"
            wish.claim_id = ""
            self.storage.upsert_wish(wish)
        self._record_rejection("reward", claim.child_id, claim.reward_id, getattr(wish, "name", ""), reason)
        await self.storage.async_save()
        await self.async_refresh()
        child = self.get_child(claim.child_id)
        self.hass.bus.async_fire(
            "taskmate_reward_rejected",
            {
                "child_id": claim.child_id,
                "child_name": getattr(child, "name", ""),
                "reward_id": claim.reward_id,
                "reward_name": getattr(wish, "name", ""),
                "wish_id": claim.wish_id,
                "claim_id": claim.id,
                "reason": reason,
                "timestamp": dt_util.now().isoformat(),
            },
        )
        await self._async_after_release([claim.id], [])
        await self._async_notify_rejected("reward", child, getattr(wish, "name", ""), reason)

    # ── internals ────────────────────────────────────────────────────────
    def _cancel_wish_claim(self, wish: Wish) -> list[str]:
        """Drop the wish's pending redemption claim, if it has one."""
        claim_id = wish.claim_id
        wish.claim_id = ""
        if not claim_id:
            return []
        claim = next((c for c in self.storage.get_reward_claims() if c.id == claim_id), None)
        if claim is None or claim.approved:
            return []
        self.storage.remove_reward_claim(claim_id)
        return [claim_id]

    def _release_wish(self, wish: Wish, why: str) -> list[str]:
        """Unwind a wish's money before it is declined or deleted.

        The child's savings go back to their balance; each pledge is voided
        (it goes back to whoever pledged it — it was never the child's). Any
        pending redemption claim is withdrawn; its id is returned so the
        caller can dismiss the parent's approval push once saved.
        """
        cancelled = self._cancel_wish_claim(wish)
        child = self.get_child(wish.child_id)
        if wish.saved > 0 and child is not None:
            child.points += wish.saved
            self.storage.update_child(child)
            self._wish_log(child.id, wish.saved, f"Wish refund ({why}): {wish.name}", count_for_season=False)
        wish.saved = 0
        if child is not None:
            for pledge in wish.pledges:
                self._wish_log(child.id, 0, f"Wish pledge voided ({pledge.name}, {pledge.points}): {wish.name}")
        wish.pledges = []
        return cancelled

    def _prune_finished_wishes(self, child_id: str, status: str, keep: int) -> list[Wish]:
        """Keep only the newest ``keep`` wishes of a finished status for a child."""
        finished = [w for w in self.storage.get_wishes() if w.child_id == child_id and w.status == status]
        if len(finished) <= keep:
            return []

        def _when(w: Wish):
            return w.redeemed_at or w.declined_at or w.created_at

        finished.sort(key=_when, reverse=True)
        dropped = finished[keep:]
        for w in dropped:
            self.storage.remove_wish(w.id)
        return dropped

    async def _async_after_release(self, cancelled_claim_ids: list[str], dropped: list[Wish]) -> None:
        """After a save: dismiss approval pushes and delete pictures no longer used."""
        if cancelled_claim_ids and getattr(self, "notifications", None):
            for claim_id in cancelled_claim_ids:
                await self.notifications.clear_approval("pending_reward_claim", claim_id)
        for wish in dropped:
            await self._async_release_wish_image(wish)

    async def _async_release_wish_image(self, wish: Wish) -> None:
        if wish.image_url:
            await images.async_delete_image(self.hass, wish.image_url)

    async def _async_remove_wishes_for_child(self, child_id: str) -> None:
        """Called when a child is deleted: their wishes (and pictures) go with them."""
        for wish in self.storage.remove_wishes_for_child(child_id):
            await self._async_release_wish_image(wish)

    def _fire_wish_event(self, event: str, wish: Wish, child, **extra) -> None:
        payload = {
            "wish_id": wish.id,
            "wish_name": wish.name,
            "child_id": wish.child_id,
            "child_name": getattr(child, "name", ""),
            "target": wish.target,
            "saved": wish.saved,
            "pledged": wish.pledged,
            "timestamp": dt_util.now().isoformat(),
            **extra,
        }
        self.hass.bus.async_fire(event, payload)

    # ── state for the panel and the card ────────────────────────────────
    def wishlist_state(self) -> list[dict]:
        """Every wish, in full, for the admin panel (images signed for <img>)."""
        out = []
        for wish in self.storage.get_wishes():
            row = wish.to_dict()
            row["pledged"] = wish.pledged
            row["remaining"] = wish.remaining
            row["funded"] = wish.funded
            if wish.image_url:
                row["image_url"] = images.sign_image_url(self.hass, wish.image_url)
            out.append(row)
        return out

    def wishlist_sensor_rows(self, child_id: str) -> list[dict]:
        """One child's wishes, compact, for the card: all but the redeemed history.

        Optional fields are only present when set, and pledges are folded
        into one chip per person (largest first, capped), because this rides
        in a sensor attribute under the recorder's 16 KB limit. The image URL
        is bare — the card signs it for the viewer.
        """
        rows = []
        for wish in self.storage.get_wishes():
            if wish.child_id != child_id or wish.status == "redeemed":
                continue
            row: dict = {
                "id": wish.id,
                "name": wish.name,
                "target": wish.target,
                "status": wish.status,
            }
            if wish.saved:
                row["saved"] = wish.saved
            if wish.pledges:
                totals: dict[str, int] = {}
                for p in wish.pledges:
                    totals[p.name] = totals.get(p.name, 0) + p.points
                row["pledged"] = wish.pledged
                row["pledges"] = [
                    {"name": n, "points": pts}
                    for n, pts in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:_SENSOR_PLEDGERS]
                ]
            if wish.link:
                row["link"] = wish.link
            if wish.image_url:
                row["image_url"] = wish.image_url
            if wish.status == "declined" and wish.decline_reason:
                row["decline_reason"] = wish.decline_reason
            rows.append(row)
        return rows
