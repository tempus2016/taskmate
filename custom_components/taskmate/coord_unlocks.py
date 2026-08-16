"""Timed unlock rewards (#678).

Spend points to unlock something for a while: the TV, the console socket, a
wifi group. Approving the claim turns the entity on; a timer turns it back off.

Two deliberate limits keep this from becoming "a reward can do anything to
your house":

  * A reward can only **turn an entity on and back off again**. There is no
    free-form service call, no payload, no template.
  * The entity must be on the parent's **allowlist**, checked both when the
    reward is saved and again when it actually fires — the allowlist can change
    after a reward was created.

Active unlocks are persisted. A Home Assistant restart mid-unlock must not
strand the television on: anything already past due is reverted at startup and
anything still running is re-armed.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

MAX_UNLOCK_MINUTES = 1440  # a day; longer belongs in an automation, not a reward


class UnlocksMixin:
    """Mixin providing allowlisted, self-reverting entity unlocks."""

    # ── allowlist ────────────────────────────────────────────────────────
    def unlock_allowlist(self) -> list[str]:
        """Entity ids and/or bare domains the parent has permitted."""
        raw = self.storage.get_setting("unlock_allowlist", [])
        if not isinstance(raw, list):
            return []
        return [str(e).strip().lower() for e in raw if str(e).strip()]

    def is_unlock_allowed(self, entity_id: str) -> bool:
        """True when ``entity_id`` is permitted by the allowlist.

        An entry may be a full entity id (``switch.xbox``) or a bare domain
        (``switch``), which permits everything in it. An empty allowlist
        permits nothing — fail closed. This gates household devices, so the
        safe default when unconfigured is "no".
        """
        entity_id = (entity_id or "").strip().lower()
        if not entity_id or "." not in entity_id:
            return False
        allow = self.unlock_allowlist()
        if not allow:
            return False
        domain = entity_id.split(".", 1)[0]
        return entity_id in allow or domain in allow

    def validate_unlock(self, entity_id: str, minutes: Any) -> tuple[str, int]:
        """Validate an unlock config, returning the cleaned pair.

        Raises ValueError with a parent-readable message.
        """
        entity_id = (entity_id or "").strip().lower()
        if not entity_id:
            return "", 0
        if not self.is_unlock_allowed(entity_id):
            raise ValueError(
                f"'{entity_id}' is not on the unlock allowlist. Add it in Settings before using it as a reward."
            )
        try:
            mins = int(minutes or 0)
        except (TypeError, ValueError) as err:
            raise ValueError("Unlock minutes must be a whole number") from err
        if mins < 0:
            raise ValueError("Unlock minutes cannot be negative")
        if mins > MAX_UNLOCK_MINUTES:
            raise ValueError(f"Unlock minutes cannot exceed {MAX_UNLOCK_MINUTES}")
        return entity_id, mins

    # ── active unlock bookkeeping ────────────────────────────────────────
    def active_unlocks(self) -> list[dict[str, Any]]:
        raw = self.storage.get_setting("active_unlocks", [])
        return [u for u in raw if isinstance(u, dict)] if isinstance(raw, list) else []

    def _store_unlocks(self, unlocks: list[dict[str, Any]]) -> None:
        self.storage.set_setting("active_unlocks", unlocks)

    async def async_start_unlock(self, reward, child) -> dict[str, Any] | None:
        """Turn on a reward's entity and schedule the revert. Returns the record.

        Returns None (and logs) rather than raising when the reward has no
        unlock configured or the entity has since left the allowlist — a
        reward approval must not fail because of a later settings change.
        """
        entity_id = (getattr(reward, "unlock_entity", "") or "").strip().lower()
        if not entity_id:
            return None

        if not self.is_unlock_allowed(entity_id):
            _LOGGER.warning(
                "Reward '%s' wanted to unlock '%s', which is no longer on the allowlist — skipping",
                reward.name,
                entity_id,
            )
            return None

        minutes = int(getattr(reward, "unlock_minutes", 0) or 0)
        await self.hass.services.async_call(
            "homeassistant",
            "turn_on",
            {"entity_id": entity_id},
            blocking=False,
        )

        record: dict[str, Any] = {
            "entity_id": entity_id,
            "reward_id": reward.id,
            "reward_name": reward.name,
            "child_id": child.id,
            "child_name": child.name,
            "started_at": dt_util.now().isoformat(),
            "revert_at": "",
        }

        if minutes > 0:
            revert_at = dt_util.now() + timedelta(minutes=minutes)
            record["revert_at"] = revert_at.isoformat()
            unlocks = self.active_unlocks()
            unlocks.append(record)
            self._store_unlocks(unlocks)
            await self.storage.async_save()
            self._schedule_revert(record, revert_at)

        _LOGGER.info(
            "Unlocked %s for %s (%s) for %s minutes",
            entity_id,
            child.name,
            reward.name,
            minutes or "no auto-revert",
        )
        self.hass.bus.async_fire("taskmate_unlock_started", dict(record))
        return record

    def _schedule_revert(self, record: dict[str, Any], when: datetime) -> None:
        async def _revert(_now) -> None:
            await self.async_revert_unlock(record)

        self._unlock_timers.append(async_track_point_in_time(self.hass, _revert, when))

    async def async_revert_unlock(self, record: dict[str, Any]) -> None:
        """Turn the entity back off and drop the record."""
        entity_id = record.get("entity_id", "")
        if entity_id:
            await self.hass.services.async_call(
                "homeassistant",
                "turn_off",
                {"entity_id": entity_id},
                blocking=False,
            )
            _LOGGER.info("Re-locked %s", entity_id)

        remaining = [
            u
            for u in self.active_unlocks()
            if not (u.get("entity_id") == entity_id and u.get("revert_at") == record.get("revert_at"))
        ]
        self._store_unlocks(remaining)
        await self.storage.async_save()
        await self.async_refresh()
        self.hass.bus.async_fire("taskmate_unlock_ended", dict(record))

    async def async_resume_unlocks(self) -> int:
        """Re-arm unlocks across a restart. Returns how many were reverted now.

        Without this a restart mid-unlock strands the entity on forever, which
        is the one genuinely bad failure mode of this feature.
        """
        now = dt_util.now()
        still_running: list[dict[str, Any]] = []
        expired: list[dict[str, Any]] = []

        for record in self.active_unlocks():
            try:
                revert_at = datetime.fromisoformat(record.get("revert_at", ""))
            except (TypeError, ValueError):
                revert_at = None
            if revert_at is not None and revert_at.tzinfo is None:
                revert_at = revert_at.replace(tzinfo=now.tzinfo)
            if revert_at is None:
                # Unparseable: revert now rather than leave it on indefinitely.
                expired.append(record)
                continue
            if revert_at <= now:
                expired.append(record)
            else:
                still_running.append(record)
                self._schedule_revert(record, revert_at)

        for record in expired:
            entity_id = record.get("entity_id", "")
            if entity_id:
                await self.hass.services.async_call(
                    "homeassistant",
                    "turn_off",
                    {"entity_id": entity_id},
                    blocking=False,
                )
                _LOGGER.info("Re-locked %s after restart (unlock had expired)", entity_id)

        if expired:
            self._store_unlocks(still_running)
            await self.storage.async_save()

        if still_running:
            _LOGGER.info("Re-armed %d active unlock(s) after restart", len(still_running))
        return len(expired)

    def cancel_unlock_timers(self) -> None:
        """Drop scheduled reverts on unload so they can't fire post-teardown."""
        # Teardown must not raise.
        for cancel in getattr(self, "_unlock_timers", []):
            with contextlib.suppress(Exception):
                cancel()
        self._unlock_timers = []
