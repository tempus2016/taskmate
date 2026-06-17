"""Avatar unlockables mixin for TaskMateCoordinator.

Parents define a catalog of avatars, each gated behind a requirement (a level,
a lifetime-points total, or a best-streak length — or ``free`` for always
available). Children unlock avatars by hitting those milestones and can switch
to any avatar they've unlocked; parents can set any catalogue avatar.
"""
from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

# Shipped defaults so the feature is useful out of the box. Parents can replace
# the whole list from the panel.
DEFAULT_AVATAR_CATALOG: list[dict] = [
    {"id": "starter", "label": "Starter",   "icon": "mdi:account-circle", "unlock_type": "free",   "unlock_value": 0},
    {"id": "rocket",  "label": "Rocket",    "icon": "mdi:rocket-launch",  "unlock_type": "level",  "unlock_value": 3},
    {"id": "robot",   "label": "Robot",     "icon": "mdi:robot-happy",    "unlock_type": "level",  "unlock_value": 5},
    {"id": "ninja",   "label": "Ninja",     "icon": "mdi:ninja",          "unlock_type": "level",  "unlock_value": 10},
    {"id": "crown",   "label": "Royalty",   "icon": "mdi:crown",          "unlock_type": "points", "unlock_value": 500},
    {"id": "trophy",  "label": "Champion",  "icon": "mdi:trophy",         "unlock_type": "points", "unlock_value": 1000},
    {"id": "fire",    "label": "On Fire",   "icon": "mdi:fire",           "unlock_type": "streak", "unlock_value": 7},
    {"id": "diamond", "label": "Diamond",   "icon": "mdi:diamond-stone",  "unlock_type": "streak", "unlock_value": 30},
]


class AvatarsMixin:
    """Mixin providing the avatar catalogue and unlock/selection logic."""

    def avatar_catalog(self) -> list[dict]:
        """The configured avatar catalogue (falls back to the shipped default)."""
        raw = self.storage.get_setting("avatar_catalog", None)
        if isinstance(raw, list) and raw:
            return [a for a in raw if isinstance(a, dict) and a.get("icon")]
        return list(DEFAULT_AVATAR_CATALOG)

    def _avatar_unlocked(self, entry: dict, child) -> bool:
        kind = entry.get("unlock_type", "free")
        try:
            value = int(entry.get("unlock_value", 0) or 0)
        except (ValueError, TypeError):
            value = 0
        if kind == "free":
            return True
        if kind == "level":
            return int(self.level_info(child)["level"]) >= value
        if kind == "points":
            return int(getattr(child, "total_points_earned", 0) or 0) >= value
        if kind == "streak":
            return int(getattr(child, "best_streak", 0) or 0) >= value
        return False

    def avatar_options_for_child(self, child) -> list[dict]:
        """Catalogue annotated with per-child unlock state (for sensors/cards)."""
        out: list[dict] = []
        for entry in self.avatar_catalog():
            kind = entry.get("unlock_type", "free")
            value = entry.get("unlock_value", 0)
            if kind == "free":
                req = ""
            elif kind == "level":
                req = f"Level {value}"
            elif kind == "points":
                req = f"{value} earned"
            elif kind == "streak":
                req = f"{value}-day streak"
            else:
                req = ""
            out.append({
                "id": entry.get("id", entry.get("icon")),
                "label": entry.get("label", ""),
                "icon": entry.get("icon"),
                "unlocked": self._avatar_unlocked(entry, child),
                "requirement": req,
            })
        return out

    async def async_update_avatar_catalog(self, catalog: list[dict]) -> None:
        """Replace the avatar catalogue (admin)."""
        cleaned: list[dict] = []
        for a in catalog:
            icon = (a.get("icon") or "").strip()
            if not icon:
                continue
            cleaned.append({
                "id": (a.get("id") or icon).strip(),
                "label": (a.get("label") or "").strip(),
                "icon": icon,
                "unlock_type": a.get("unlock_type", "free"),
                "unlock_value": int(a.get("unlock_value", 0) or 0),
            })
        self.storage.set_setting("avatar_catalog", cleaned)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_set_avatar(self, child_id: str, icon: str, enforce_unlock: bool = True) -> None:
        """Set a child's avatar.

        When ``enforce_unlock`` (child self-service) the icon must be an
        unlocked catalogue avatar; parents may set any catalogue avatar.
        """
        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")
        catalog = self.avatar_catalog()
        entry = next((a for a in catalog if a.get("icon") == icon or a.get("id") == icon), None)
        if not entry:
            raise ValueError("That avatar is not in the catalogue")
        if enforce_unlock and not self._avatar_unlocked(entry, child):
            raise ValueError("That avatar is not unlocked yet")
        child.avatar = entry.get("icon")
        self.storage.update_child(child)
        await self.storage.async_save()
        await self.async_refresh()
