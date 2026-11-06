"""Pet shop: fixed-cost cosmetics a child buys for their virtual pet.

Off until a parent turns it on (Settings → Virtual pets → Pet shop). The
parent keeps a catalogue of items — a name, an emoji, the slot it goes in, a
fixed cost and an optional level gate — and can hide any of them. Prices are
whatever the parent typed: nothing here ever works a price out.

A child buys from the pet card's Shop tab. The cost comes out of the spendable
wallet (``child.points``) only — never a pool or savings jar — and lands in the
transaction history as ``Pet shop: <item>``. When a parent sets "purchases
over N points need a parent's OK", a dearer item becomes a pending purchase
instead: the parents get a push and decide in the panel, and the points only
move on approval.

Each child has a wardrobe: what they own and what is worn, one item per slot.
The level accessories (bow, top hat, scarf, crown) are part of it for free. A
family that never opens the shop sees exactly what it always did: an earned
accessory is worn by default, best one per slot (the crown over the top hat,
the scarf over the bow), until the child takes it off. Taking one off is
remembered as an empty slot.

With "bought items carry over to the next pet" off, hatching a new pet empties
the wardrobe, so the new pet starts fresh.
"""

from __future__ import annotations

import re
from typing import Any

from homeassistant.util import dt as dt_util

from .const import NOTIF_TYPE_PET_ITEM_REQUESTED
from .errors import TaskMateError
from .models import PointsTransaction, generate_id

PET_SHOP_SLOTS = ("hat", "face", "neck", "held", "back", "body", "colour", "home")
PET_SHOP_NAME_MAX = 30
PET_SHOP_EMOJI_MAX = 8
PET_SHOP_COST_MAX = 100_000
PET_SHOP_LEVEL_MAX = 999
PET_SHOP_MAX_ITEMS = 60
# Owned ids ride on the sensor only while the list is this short.
PET_SHOP_OWNED_ON_SENSOR = 40
PET_SHOP_REASON = "Pet shop: "
PET_ITEM_BOUGHT_EVENT = "taskmate_pet_item_bought"

# The level accessories and the slot each one goes in.
PET_ACCESSORY_SLOTS = {"bow": "neck", "top_hat": "hat", "scarf": "neck", "crown": "hat"}
# Which earned accessory is worn by default, best first.
_DEFAULT_WORN = {"hat": ("crown", "top_hat"), "neck": ("scarf", "bow")}

_TINT_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_EMOJI_BAD = re.compile(r"[<>&\"'\x00-\x1f\x7f]")

# The catalogue a family starts with. Default items carry no stored name: the
# cards show a translated one until a parent renames it. ``DEFAULT_NAMES`` is
# the English used for the transaction reason and the parents' push.
PET_SHOP_DEFAULTS: tuple[dict[str, Any], ...] = (
    {"id": "sunglasses", "emoji": "🕶️", "slot": "face", "cost": 15, "level": 0, "shown": True},
    {"id": "cap", "emoji": "🧢", "slot": "hat", "cost": 20, "level": 0, "shown": True},
    {"id": "balloon", "emoji": "🎈", "slot": "held", "cost": 25, "level": 0, "shown": True},
    {"id": "cosy_bed", "emoji": "🛏️", "slot": "home", "cost": 40, "level": 0, "shown": True},
    {"id": "rainbow", "emoji": "🌈", "slot": "colour", "cost": 60, "level": 0, "shown": True, "tint": "rainbow"},
    {"id": "wings", "emoji": "🦋", "slot": "back", "cost": 80, "level": 12, "shown": True},
    {"id": "ghost_sheet", "emoji": "👻", "slot": "body", "cost": 30, "level": 0, "shown": False},
)
DEFAULT_NAMES = {
    "sunglasses": "Sunglasses",
    "cap": "Cap",
    "balloon": "Balloon",
    "cosy_bed": "Cosy bed",
    "rainbow": "Rainbow colour",
    "wings": "Wings",
    "ghost_sheet": "Ghost sheet",
}
_DEFAULT_IDS = frozenset(DEFAULT_NAMES)


def _default_catalogue() -> list[dict[str, Any]]:
    return [{"name": "", "tint": "", **item} for item in PET_SHOP_DEFAULTS]


def _clean_emoji(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > PET_SHOP_EMOJI_MAX or _EMOJI_BAD.search(text):
        raise TaskMateError("pet_shop_emoji_invalid", max=PET_SHOP_EMOJI_MAX)
    return text


def _clean_tint(value: Any) -> str:
    text = str(value or "").strip()
    if text in ("", "rainbow") or _TINT_RE.match(text):
        return text.lower() if text.startswith("#") else text
    raise TaskMateError("pet_shop_colour_invalid")


class PetShopMixin:
    """The pet shop catalogue, purchases, approvals and each child's wardrobe."""

    # ── settings ───────────────────────────────────────────────────────

    def pet_shop_enabled(self) -> bool:
        return self.pets_enabled() and self._pet_on("pet_shop_enabled")

    def pet_shop_approve_over(self) -> int:
        return self._pet_int("pet_shop_approve_over")

    def pet_shop_carry_over(self) -> bool:
        return self._pet_on("pet_shop_carry_over")

    # ── catalogue ──────────────────────────────────────────────────────

    def pet_shop_items(self) -> list[dict[str, Any]]:
        """The parent's catalogue (the default one until they change it)."""
        items = self.storage.data.get("pet_shop_items")
        if not isinstance(items, list):
            return _default_catalogue()
        return [i for i in items if isinstance(i, dict) and i.get("id")]

    def _pet_shop_item(self, item_id: str) -> dict[str, Any] | None:
        return next((i for i in self.pet_shop_items() if i.get("id") == item_id), None)

    @staticmethod
    def pet_item_name(item: dict[str, Any]) -> str:
        return str(item.get("name") or DEFAULT_NAMES.get(item.get("id", ""), item.get("id", "")))

    async def async_save_pet_shop_item(
        self,
        item_id: str | None,
        *,
        name: str = "",
        emoji: str,
        slot: str,
        cost: int,
        level: int = 0,
        shown: bool = True,
        tint: str = "",
    ) -> dict[str, Any]:
        """Add (no ``item_id``) or change a catalogue item. Costs are fixed whole numbers."""
        items = self.pet_shop_items()
        existing = next((i for i in items if i.get("id") == item_id), None) if item_id else None
        if item_id and existing is None:
            raise TaskMateError("pet_shop_item_not_found")
        name = (name or "").strip()
        if len(name) > PET_SHOP_NAME_MAX:
            raise TaskMateError("pet_shop_name_too_long", max=PET_SHOP_NAME_MAX)
        if not name and not (existing and existing["id"] in _DEFAULT_IDS):
            raise TaskMateError("pet_shop_name_required")
        if slot not in PET_SHOP_SLOTS:
            raise TaskMateError("pet_shop_unknown_slot", slot=repr(slot))
        try:
            cost = int(cost)
            level = int(level or 0)
        except (TypeError, ValueError) as err:
            raise TaskMateError("pet_shop_not_whole") from err
        if not 1 <= cost <= PET_SHOP_COST_MAX:
            raise TaskMateError("pet_shop_cost_range", max=PET_SHOP_COST_MAX)
        if not 0 <= level <= PET_SHOP_LEVEL_MAX:
            raise TaskMateError("pet_shop_level_range", max=PET_SHOP_LEVEL_MAX)
        fields = {
            "name": name,
            "emoji": _clean_emoji(emoji),
            "slot": slot,
            "cost": cost,
            "level": level,
            "shown": bool(shown),
            "tint": _clean_tint(tint) if slot == "colour" else "",
        }
        if existing is not None:
            existing.update(fields)
        else:
            if len(items) >= PET_SHOP_MAX_ITEMS:
                raise TaskMateError("pet_shop_full", max=PET_SHOP_MAX_ITEMS)
            existing = {"id": generate_id(), **fields}
            items.append(existing)
        self.storage.data["pet_shop_items"] = items
        await self.storage.async_save()
        await self.async_refresh()
        return existing

    async def async_set_pet_shop_item_shown(self, item_id: str, shown: bool) -> None:
        items = self.pet_shop_items()
        item = next((i for i in items if i.get("id") == item_id), None)
        if item is None:
            raise TaskMateError("pet_shop_item_not_found")
        item["shown"] = bool(shown)
        self.storage.data["pet_shop_items"] = items
        await self.storage.async_save()
        await self.async_refresh()

    async def async_remove_pet_shop_item(self, item_id: str) -> None:
        """Take an item out of the shop. Children who bought it simply stop wearing it."""
        items = self.pet_shop_items()
        if not any(i.get("id") == item_id for i in items):
            raise TaskMateError("pet_shop_item_not_found")
        self.storage.data["pet_shop_items"] = [i for i in items if i.get("id") != item_id]
        self._drop_orphan_pet_purchases()
        await self.storage.async_save()
        await self.async_refresh()

    async def async_reset_pet_shop_items(self) -> None:
        """Put the default catalogue back (custom items go)."""
        self.storage.data["pet_shop_items"] = _default_catalogue()
        self._drop_orphan_pet_purchases()
        await self.storage.async_save()
        await self.async_refresh()

    # ── wardrobe ───────────────────────────────────────────────────────

    def _pet_wardrobes(self) -> dict[str, dict[str, Any]]:
        return self.storage.get_section("pet_wardrobe", dict)

    def _pet_wardrobe(self, child_id: str, create: bool = False) -> dict[str, Any]:
        wardrobes = self._pet_wardrobes()
        entry = wardrobes.get(child_id)
        if not isinstance(entry, dict):
            entry = {}
            if create:
                wardrobes[child_id] = entry
        if create:
            if not isinstance(entry.get("owned"), list):
                entry["owned"] = []
            if not isinstance(entry.get("equipped"), dict):
                entry["equipped"] = {}
        return entry

    def pet_owned(self, child_id: str) -> list[str]:
        owned = self._pet_wardrobe(child_id).get("owned")
        return [str(i) for i in owned] if isinstance(owned, list) else []

    @staticmethod
    def _earned_accessories(child) -> list[str]:
        from .coord_pets import PET_ACCESSORIES

        level = int(getattr(child, "level", 1) or 1)
        return [acc for acc, at in PET_ACCESSORIES if level >= at]

    def pet_worn(self, child) -> dict[str, dict[str, Any]]:
        """What the pet wears, slot by slot: ``{slot: {"id", "emoji"[, "tint"]}}``.

        Earned accessories are worn by default (best per slot) unless the child
        took them off. A worn item that left the catalogue falls back to that
        default.
        """
        earned = self._earned_accessories(child)
        wardrobe = self._pet_wardrobe(child.id)
        equipped = wardrobe.get("equipped") if isinstance(wardrobe.get("equipped"), dict) else {}
        owned = set(self.pet_owned(child.id))
        catalogue = {i["id"]: i for i in self.pet_shop_items()}
        worn: dict[str, dict[str, Any]] = {}
        for slot in PET_SHOP_SLOTS:
            choice = equipped.get(slot)
            if choice == "":
                continue
            if choice:
                if choice in earned and PET_ACCESSORY_SLOTS.get(choice) == slot:
                    worn[slot] = {"id": choice}
                    continue
                item = catalogue.get(choice)
                if item is not None and choice in owned and item.get("slot") == slot:
                    entry = {"id": choice, "emoji": item.get("emoji", "")}
                    if item.get("tint"):
                        entry["tint"] = item["tint"]
                    worn[slot] = entry
                    continue
            for acc in _DEFAULT_WORN.get(slot, ()):
                if acc in earned:
                    worn[slot] = {"id": acc}
                    break
        return worn

    def pet_shop_state(self, child) -> dict[str, Any]:
        """The compact shop fields for the child's pet on the sensor."""
        out: dict[str, Any] = {}
        has_wardrobe = isinstance(self._pet_wardrobes().get(child.id), dict)
        if has_wardrobe or self.pet_shop_enabled():
            out["worn"] = self.pet_worn(child)
        if not self.pet_shop_enabled():
            return out
        shop: dict[str, Any] = {}
        owned = self.pet_owned(child.id)
        if owned and len(owned) <= PET_SHOP_OWNED_ON_SENSOR:
            shop["owned"] = owned
        pending = [p["item_id"] for p in self._pet_purchases() if p.get("child_id") == child.id]
        if pending:
            shop["pending"] = pending
        if (over := self.pet_shop_approve_over()) > 0:
            shop["approve_over"] = over
        out["shop"] = shop
        return out

    def pet_shop_for_child(self, child_id: str) -> dict[str, Any]:
        """What the card's Shop tab needs, fetched over the WebSocket."""
        child = self.get_child(child_id)
        if child is None:
            raise TaskMateError("child_not_found", child_id=child_id)
        owned = self.pet_owned(child_id)
        items = [
            {
                k: i.get(k)
                for k in ("id", "name", "emoji", "slot", "cost", "level", "tint")
                if i.get(k) not in (None, "")
            }
            for i in self.pet_shop_items()
            if i.get("shown") or i.get("id") in owned
        ]
        for item in items:
            if not item.get("name"):
                item["default"] = True
        return {
            "enabled": self.pet_shop_enabled(),
            "items": items,
            "owned": owned,
            "pending": [p["item_id"] for p in self._pet_purchases() if p.get("child_id") == child_id],
            "earned": self._earned_accessories(child),
            "worn": self.pet_worn(child),
            "approve_over": self.pet_shop_approve_over(),
            "carry_over": self.pet_shop_carry_over(),
            "spendable": self._pet_shop_spendable(child),
            "level": int(getattr(child, "level", 1) or 1),
        }

    def _pet_shop_on_hatch(self, child_id: str) -> None:
        """A new pet hatched: with carry-over off it starts with an empty wardrobe."""
        if not self.pet_shop_carry_over():
            self._pet_wardrobes().pop(child_id, None)

    async def async_equip_pet_item(self, child_id: str, item_id: str, on: bool = True) -> dict[str, Any]:
        """Put an item on (replacing whatever is in its slot) or take it off."""
        child = self.get_child(child_id)
        if child is None:
            raise TaskMateError("child_not_found", child_id=child_id)
        if not self.pets_enabled():
            raise TaskMateError("pets_switched_off")
        if not self._pets().get(child_id):
            raise TaskMateError("pet_adopt_first")
        if item_id in PET_ACCESSORY_SLOTS:
            if item_id not in self._earned_accessories(child):
                raise TaskMateError("pet_shop_not_unlocked")
            slot = PET_ACCESSORY_SLOTS[item_id]
        else:
            if not self.pet_shop_enabled():
                raise TaskMateError("pet_shop_closed")
            item = self._pet_shop_item(item_id)
            if item is None:
                raise TaskMateError("pet_shop_item_not_found")
            if item_id not in self.pet_owned(child_id):
                raise TaskMateError("pet_shop_buy_first")
            slot = item["slot"]
        worn_now = self.pet_worn(child).get(slot, {}).get("id")
        wardrobe = self._pet_wardrobe(child_id, create=True)
        if on:
            wardrobe["equipped"][slot] = item_id
        elif worn_now == item_id:
            wardrobe["equipped"][slot] = ""
        await self.storage.async_save()
        await self.async_refresh()
        return self.pet_worn(child)

    # ── buying ─────────────────────────────────────────────────────────

    def _pet_purchases(self) -> list[dict[str, Any]]:
        return self.storage.get_section("pet_shop_pending", list)

    def _drop_orphan_pet_purchases(self) -> None:
        ids = {i["id"] for i in self.pet_shop_items()}
        self.storage.data["pet_shop_pending"] = [p for p in self._pet_purchases() if p.get("item_id") in ids]

    def _pet_shop_spendable(self, child, *, skip_purchase: str = "") -> int:
        """The wallet less what's already promised: rewards and pet items awaiting a parent."""
        committed = 0
        for claim in self.storage.get_pending_reward_claims():
            if claim.child_id != child.id or self.is_pool_mode_claim(claim):
                continue
            reward = self.get_reward(claim.reward_id)
            committed += reward.cost if reward else 0
        for purchase in self._pet_purchases():
            if purchase.get("child_id") == child.id and purchase.get("id") != skip_purchase:
                committed += int(purchase.get("cost", 0) or 0)
        return max(0, int(child.points or 0) - committed)

    async def async_buy_pet_item(self, child_id: str, item_id: str) -> dict[str, Any]:
        """Buy an item now, or ask a parent first when it costs over the threshold.

        Returns ``{"status": "bought"}`` or ``{"status": "pending", "purchase_id": ...}``.
        """
        child = self.get_child(child_id)
        if child is None:
            raise TaskMateError("child_not_found", child_id=child_id)
        if not self.pets_enabled():
            raise TaskMateError("pets_switched_off")
        if not self.pet_shop_enabled():
            raise TaskMateError("pet_shop_closed")
        pet = self._pets().get(child_id)
        if not pet:
            raise TaskMateError("pet_adopt_first")
        item = self._pet_shop_item(item_id)
        if item is None or not item.get("shown"):
            raise TaskMateError("pet_shop_not_for_sale")
        level = int(getattr(child, "level", 1) or 1)
        if int(item.get("level", 0) or 0) > level:
            raise TaskMateError("pet_shop_unlocks_at_level", level=item["level"])
        if item_id in self.pet_owned(child_id):
            raise TaskMateError("pet_shop_already_owned")
        if any(p.get("child_id") == child_id and p.get("item_id") == item_id for p in self._pet_purchases()):
            raise TaskMateError("pet_shop_already_pending")
        cost = int(item["cost"])
        if self._pet_shop_spendable(child) < cost:
            raise TaskMateError("pet_shop_not_enough_points")
        name = self.pet_item_name(item)
        over = self.pet_shop_approve_over()
        if over > 0 and cost > over:
            purchase = {
                "id": generate_id(),
                "child_id": child_id,
                "item_id": item_id,
                "cost": cost,
                "requested_at": dt_util.now().isoformat(),
            }
            self._pet_purchases().append(purchase)
            await self.storage.async_save()
            await self.notifications.fire(
                NOTIF_TYPE_PET_ITEM_REQUESTED,
                {
                    "child_id": child_id,
                    "child_name": child.name,
                    "pet_name": pet.get("name", ""),
                    "item_name": name,
                    "cost": cost,
                    "points_name": self.storage.get_points_name(),
                },
            )
            await self.async_refresh()
            return {"status": "pending", "purchase_id": purchase["id"]}
        self._pet_shop_pay(child, item_id, name, cost)
        await self.storage.async_save()
        await self.async_refresh()
        return {"status": "bought"}

    def _pet_shop_pay(self, child, item_id: str, name: str, cost: int) -> None:
        """Take the cost from the wallet, hand the item over and tell the bus."""
        child.points = int(child.points or 0) - cost
        self.storage.update_child(child)
        self.storage.add_points_transaction(
            PointsTransaction(
                child_id=child.id,
                points=-cost,
                reason=f"{PET_SHOP_REASON}{name}",
                created_at=dt_util.now(),
                reason_key="pet_shop",
                reason_params={"name": name},
            )
        )
        wardrobe = self._pet_wardrobe(child.id, create=True)
        if item_id not in wardrobe["owned"]:
            wardrobe["owned"].append(item_id)
        self.hass.bus.async_fire(
            PET_ITEM_BOUGHT_EVENT,
            {"child_id": child.id, "child_name": child.name, "item_id": item_id, "item_name": name, "cost": cost},
        )

    def pet_shop_pending_state(self) -> list[dict[str, Any]]:
        """Pending purchases for the panel, oldest first."""
        out = []
        for p in self._pet_purchases():
            child = self.get_child(p.get("child_id", ""))
            item = self._pet_shop_item(p.get("item_id", ""))
            if child is None or item is None:
                continue
            out.append(
                {
                    "id": p["id"],
                    "child_id": child.id,
                    "child_name": child.name,
                    "item_id": item["id"],
                    "item_name": item.get("name", ""),
                    "emoji": item.get("emoji", ""),
                    "cost": int(p.get("cost", 0) or 0),
                    "requested_at": p.get("requested_at", ""),
                }
            )
        return out

    async def async_decide_pet_purchase(self, purchase_id: str, approve: bool) -> None:
        """Approve (the points move now) or decline (nothing is taken) a pending purchase."""
        purchases = self._pet_purchases()
        purchase = next((p for p in purchases if p.get("id") == purchase_id), None)
        if purchase is None:
            raise TaskMateError("pet_shop_purchase_gone")
        if approve:
            child = self.get_child(purchase.get("child_id", ""))
            item = self._pet_shop_item(purchase.get("item_id", ""))
            if child is None or item is None:
                raise TaskMateError("pet_shop_purchase_orphaned")
            cost = int(purchase.get("cost", 0) or 0)
            if purchase["item_id"] not in self.pet_owned(child.id):
                if self._pet_shop_spendable(child, skip_purchase=purchase_id) < cost:
                    raise TaskMateError("pet_shop_child_cannot_afford", child_name=child.name)
                self._pet_shop_pay(child, item["id"], self.pet_item_name(item), cost)
        self.storage.data["pet_shop_pending"] = [p for p in purchases if p.get("id") != purchase_id]
        await self.storage.async_save()
        await self.async_refresh()
