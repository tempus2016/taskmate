"""Raffles: children buy tickets with points, one is drawn for a big prize.

A parent sets up a raffle — a prize, a fixed ticket price, an optional cap per
child, and when it is drawn. Children spend points on tickets (one ticket, one
chance); at the draw time a winner is picked at random weighted by tickets,
and the draw is shown on the kiosk and the raffle card. Ticket prices never
change once a raffle opens: no dynamic pricing.

A cancelled raffle refunds every ticket. A raffle nobody entered closes with
no winner.
"""

from __future__ import annotations

import logging
import random
from datetime import timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import NOTIF_TYPE_RAFFLE_DRAWN
from .models import PointsTransaction, generate_id, parse_datetime

_LOGGER = logging.getLogger(__name__)

RAFFLE_NAME_MAX = 80
RAFFLE_PRIZE_MAX = 120
RAFFLE_TICKET_COST_MAX = 100000
RAFFLE_MAX_TICKETS = 100
# Drawn and cancelled raffles stay visible this long, then leave the cards.
RAFFLE_SHOW_DONE_HOURS = 24
RAFFLES_KEEP = 50


def _trim_finished(records: list, limit: int, keep: tuple[str, ...]) -> None:
    """Drop the oldest finished records past ``limit``; live ones (``keep``) always stay."""
    excess = len(records) - limit
    if excess <= 0:
        return
    drop = [r for r in records if r.get("status") not in keep][:excess]
    for record in drop:
        records.remove(record)


class RafflesMixin:
    """Ticket raffles."""

    def _raffles(self) -> list[dict[str, Any]]:
        return self.storage.get_section("raffles", list)

    def get_raffle(self, raffle_id: str) -> dict[str, Any] | None:
        return next((r for r in self._raffles() if r.get("id") == raffle_id), None)

    # ── Parent side ──────────────────────────────────────────────────────

    def _clean_raffle_fields(self, data: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if "name" in data:
            name = str(data["name"] or "").strip()[:RAFFLE_NAME_MAX]
            if not name:
                raise ValueError("Give the raffle a name.")
            out["name"] = name
        if "prize" in data:
            out["prize"] = str(data["prize"] or "").strip()[:RAFFLE_PRIZE_MAX]
        if "icon" in data:
            out["icon"] = str(data["icon"] or "mdi:ticket-confirmation").strip()[:60]
        if "ticket_cost" in data:
            cost = int(data["ticket_cost"])
            if not 1 <= cost <= RAFFLE_TICKET_COST_MAX:
                raise ValueError(f"A ticket costs 1 to {RAFFLE_TICKET_COST_MAX}.")
            out["ticket_cost"] = cost
        if "max_tickets" in data:
            out["max_tickets"] = max(0, min(RAFFLE_MAX_TICKETS, int(data["max_tickets"] or 0)))
        if "draw_at" in data:
            when = parse_datetime(data["draw_at"])
            if when is None:
                raise ValueError("Pick when the raffle is drawn.")
            out["draw_at"] = when.isoformat()
        if "assigned_to" in data:
            out["assigned_to"] = [str(c) for c in (data["assigned_to"] or [])]
        return out

    async def async_create_raffle(self, **data: Any) -> dict[str, Any]:
        fields = self._clean_raffle_fields(
            {"icon": "mdi:ticket-confirmation", "max_tickets": 0, "assigned_to": [], "prize": "", **data}
        )
        for key in ("name", "ticket_cost", "draw_at"):
            if key not in fields:
                raise ValueError(f"{key} is required")
        if parse_datetime(fields["draw_at"]) <= dt_util.now():
            raise ValueError("The draw has to be in the future.")
        raffle = {
            "id": generate_id(),
            **fields,
            "status": "open",
            "tickets": {},
            "created_at": dt_util.now().isoformat(),
        }
        raffles = self._raffles()
        raffles.append(raffle)
        _trim_finished(raffles, RAFFLES_KEEP, keep=("open",))
        await self.storage.async_save()
        await self.async_refresh()
        return raffle

    async def async_update_raffle(self, raffle_id: str, **data: Any) -> dict[str, Any]:
        raffle = self.get_raffle(raffle_id)
        if raffle is None:
            raise ValueError("Raffle not found")
        if raffle.get("status") != "open":
            raise ValueError("Only an open raffle can be changed.")
        fields = self._clean_raffle_fields(data)
        # Fixed prices: once anyone has bought in, the ticket price is set.
        if "ticket_cost" in fields and fields["ticket_cost"] != raffle.get("ticket_cost") and raffle.get("tickets"):
            raise ValueError("Tickets have been bought, so the price can't change.")
        raffle.update(fields)
        await self.storage.async_save()
        await self.async_refresh()
        return raffle

    async def async_cancel_raffle(self, raffle_id: str) -> None:
        """Call a raffle off and give every ticket's points back."""
        raffle = self.get_raffle(raffle_id)
        if raffle is None:
            raise ValueError("Raffle not found")
        if raffle.get("status") == "open":
            cost = int(raffle.get("ticket_cost", 0) or 0)
            for child_id, count in list((raffle.get("tickets") or {}).items()):
                child = self.get_child(child_id)
                if child is None or not count:
                    continue
                refund = cost * int(count)
                child.points += refund
                self.storage.update_child(child)
                self.storage.add_points_transaction(
                    PointsTransaction(
                        child_id=child_id,
                        points=refund,
                        reason=f"Raffle called off: {raffle.get('name', '')}",
                        created_at=dt_util.now(),
                    )
                )
            raffle["status"] = "cancelled"
            raffle["closed_at"] = dt_util.now().isoformat()
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_raffle(self, raffle_id: str) -> None:
        raffle = self.get_raffle(raffle_id)
        if raffle is None:
            raise ValueError("Raffle not found")
        if raffle.get("status") == "open" and raffle.get("tickets"):
            await self.async_cancel_raffle(raffle_id)
        self.storage.data["raffles"] = [r for r in self._raffles() if r.get("id") != raffle_id]
        await self.storage.async_save()
        await self.async_refresh()

    # ── Child side ───────────────────────────────────────────────────────

    def raffle_open_to(self, raffle: dict[str, Any], child_id: str) -> bool:
        assigned = raffle.get("assigned_to") or []
        return not assigned or child_id in assigned

    async def async_buy_raffle_tickets(self, raffle_id: str, child_id: str, tickets: int) -> int:
        """Spend points on ``tickets`` tickets. Returns the child's ticket count."""
        raffle = self.get_raffle(raffle_id)
        if raffle is None:
            raise ValueError("Raffle not found")
        child = self.get_child(child_id)
        if child is None:
            raise ValueError(f"Child {child_id} not found")
        if raffle.get("status") != "open":
            raise ValueError("This raffle has closed.")
        if parse_datetime(raffle.get("draw_at")) <= dt_util.now():
            raise ValueError("This raffle is being drawn.")
        if not self.raffle_open_to(raffle, child_id):
            raise ValueError(f"This raffle isn't open to {child.name}.")
        tickets = int(tickets)
        if tickets < 1:
            raise ValueError("Buy at least one ticket.")
        held = int((raffle.get("tickets") or {}).get(child_id, 0) or 0)
        cap = int(raffle.get("max_tickets", 0) or 0)
        if cap and held + tickets > cap:
            raise ValueError(f"You can hold at most {cap} tickets.")
        cost = int(raffle.get("ticket_cost", 0) or 0) * tickets
        # Points already promised to a reward waiting for approval aren't spendable.
        committed = 0
        for claim in self.storage.get_pending_reward_claims():
            if claim.child_id == child_id and not self.is_pool_mode_claim(claim):
                pending = self.get_reward(claim.reward_id)
                committed += pending.cost if pending else 0
        if child.points - committed < cost:
            raise ValueError("Not enough points for that many tickets.")
        child.points -= cost
        self.storage.update_child(child)
        self.storage.add_points_transaction(
            PointsTransaction(
                child_id=child_id,
                points=-cost,
                reason=f"Raffle tickets ×{tickets}: {raffle.get('name', '')}",
                created_at=dt_util.now(),
            )
        )
        raffle.setdefault("tickets", {})[child_id] = held + tickets
        await self.storage.async_save()
        await self.async_refresh()
        return held + tickets

    # ── The draw ─────────────────────────────────────────────────────────

    async def async_draw_raffle(self, raffle_id: str, rng: random.Random | None = None) -> str:
        """Pick the winner now. Returns the winning child id ("" when nobody entered)."""
        raffle = self.get_raffle(raffle_id)
        if raffle is None:
            raise ValueError("Raffle not found")
        if raffle.get("status") != "open":
            raise ValueError("This raffle has already closed.")
        entries = [(cid, int(n)) for cid, n in (raffle.get("tickets") or {}).items() if int(n or 0) > 0]
        entries = [(cid, n) for cid, n in entries if self.get_child(cid) is not None]
        winner = ""
        if entries:
            pick = (rng or random).randrange(sum(n for _, n in entries))
            for cid, n in entries:
                if pick < n:
                    winner = cid
                    break
                pick -= n
        raffle["status"] = "drawn"
        raffle["winner_id"] = winner
        raffle["drawn_at"] = dt_util.now().isoformat()
        await self.storage.async_save()
        total = sum(n for _, n in entries)
        child = self.get_child(winner) if winner else None
        if child is not None:
            self.hass.bus.async_fire(
                "taskmate_raffle_won",
                {
                    "child_id": winner,
                    "child_name": child.name,
                    "raffle_id": raffle_id,
                    "raffle_name": raffle.get("name", ""),
                    "prize": raffle.get("prize", ""),
                    "tickets": dict(raffle.get("tickets") or {}).get(winner, 0),
                    "timestamp": dt_util.now().isoformat(),
                },
            )
        await self.notifications.fire(
            NOTIF_TYPE_RAFFLE_DRAWN,
            {
                "raffle_id": raffle_id,
                "raffle_name": raffle.get("name", ""),
                "prize": raffle.get("prize", ""),
                "winner_id": winner,
                "winner_name": child.name if child else "—",
                "tickets": total,
            },
        )
        await self.async_refresh()
        return winner

    async def async_draw_due_raffles(self) -> int:
        """Draw every open raffle whose time has come (the minutely check)."""
        now = dt_util.now()
        due = [
            r["id"]
            for r in self._raffles()
            if r.get("status") == "open" and (parse_datetime(r.get("draw_at")) or now) <= now
        ]
        for raffle_id in due:
            await self.async_draw_raffle(raffle_id)
        return len(due)

    def raffles_state(self) -> list[dict[str, Any]]:
        """Open raffles and ones drawn in the last day, for the cards."""
        now = dt_util.now()
        cutoff = now - timedelta(hours=RAFFLE_SHOW_DONE_HOURS)
        out = []
        for r in self._raffles():
            status = r.get("status")
            if status != "open":
                closed = parse_datetime(r.get("drawn_at") or r.get("closed_at"))
                if closed is None or closed < cutoff:
                    continue
            tickets = {k: int(v) for k, v in (r.get("tickets") or {}).items() if int(v or 0) > 0}
            row = {
                "id": r["id"],
                "name": r.get("name", ""),
                "prize": r.get("prize", ""),
                "icon": r.get("icon", "mdi:ticket-confirmation"),
                "cost": int(r.get("ticket_cost", 0) or 0),
                "draw_at": r.get("draw_at", ""),
                "status": status,
                "tickets": tickets,
                "total": sum(tickets.values()),
            }
            if r.get("max_tickets"):
                row["max"] = int(r["max_tickets"])
            if r.get("assigned_to"):
                row["assigned_to"] = list(r["assigned_to"])
            if status == "drawn":
                row["winner_id"] = r.get("winner_id", "")
                row["drawn_at"] = r.get("drawn_at", "")
            out.append(row)
        return out

    def all_raffles(self) -> list[dict[str, Any]]:
        """Every stored raffle, newest first, for the admin panel."""
        return sorted(self._raffles(), key=lambda r: r.get("created_at", ""), reverse=True)
