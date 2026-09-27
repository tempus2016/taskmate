"""Teamwork chores (#928) mixin for TaskMateCoordinator.

A teamwork chore only counts once ``team_size`` different children have joined
the day's occurrence. Each child's Done tap goes through the ordinary
``async_complete_chore`` gates and then lands here as a *join*; the join that
fills the team records a completion for every participant at once, through the
normal approval rules. Joins live in ``storage["team_joins"]`` keyed by chore
and dated, so they reset on their own when the day — the occurrence — rolls
over, and a chore edit can never touch them.
"""

from __future__ import annotations

import logging

from homeassistant.util import dt as dt_util

from .const import TEAM_POINTS_MODES, TEAM_SIZE_MAX

_LOGGER = logging.getLogger(__name__)

# A team is several children doing the same job side by side. Rotation modes
# hand the chore to one child a day and first-come hands it to whoever is
# fastest, so neither can ever gather a team.
_TEAM_ASSIGNMENT_MODES = frozenset({"everyone", "unassigned"})


def teamwork_config_error(
    team_size: int,
    *,
    assignment_mode: str = "everyone",
    open_ended: bool = False,
    task_type: str = "standard",
    team_points_mode: str = "each",
) -> str | None:
    """Why a chore's teamwork settings can't be saved, or None when they can.

    Shared by the panel's WebSocket commands, the add_chore service and the
    coordinator, so every way in refuses the same combinations.
    """
    try:
        size = int(team_size or 0)
    except (TypeError, ValueError):
        return "Team size must be a whole number."
    if size == 0:
        return None
    if size < 2 or size > TEAM_SIZE_MAX:
        return f"A teamwork chore needs between 2 and {TEAM_SIZE_MAX} children (or 0 for a normal chore)."
    if team_points_mode not in TEAM_POINTS_MODES:
        return "Team points must be 'each' or 'split'."
    if open_ended:
        return "A teamwork chore can't also be open-ended."
    if assignment_mode not in _TEAM_ASSIGNMENT_MODES:
        return "A teamwork chore must be assigned to everyone — not first-come or a rotation."
    if task_type != "standard":
        return "A timed task can't be a teamwork chore."
    return None


class TeamworkMixin:
    """Mixin providing teamwork chore joins and team completion."""

    def teamwork_size(self, chore) -> int:
        """The team a chore needs, or 0 when it isn't (validly) a teamwork chore.

        Re-checks the combination rules at read time, so a chore that reached
        storage some other way (an old backup, a template pack) behaves as an
        ordinary chore rather than as a team nobody can complete.
        """
        size = int(getattr(chore, "team_size", 0) or 0)
        if size < 2:
            return 0
        error = teamwork_config_error(
            size,
            assignment_mode=getattr(chore, "assignment_mode", "everyone"),
            open_ended=bool(getattr(chore, "open_ended", False)),
            task_type=getattr(chore, "task_type", "standard") or "standard",
            team_points_mode=getattr(chore, "team_points_mode", "each"),
        )
        return 0 if error else size

    def team_share_points(self, chore) -> int:
        """What each participant earns before time/speed/roulette adjustments.

        ``split`` divides the difficulty-scaled points evenly, rounded down;
        ``team_bonus`` is then added per participant in either mode.
        """
        base = self.effective_chore_points(chore)
        size = self.teamwork_size(chore)
        if not size:
            return base
        if getattr(chore, "team_points_mode", "each") == "split":
            base //= size
        return base + max(0, int(getattr(chore, "team_bonus", 0) or 0))

    def team_joined_ids(self, chore) -> list[str]:
        """Child IDs that have joined today's occurrence, in join order."""
        if not self.teamwork_size(chore):
            return []
        day = dt_util.as_local(dt_util.now()).date().isoformat()
        return [j["child_id"] for j in self.storage.get_team_joins(chore.id, day)]

    async def _async_join_team_chore(self, chore, child, now, *, as_parent: bool = False, photo_url: str = ""):
        """Add ``child`` to today's team; complete it for everyone once it's full.

        Called from ``async_complete_chore`` after every eligibility gate has
        passed for this child. Returns the caller's completion when this join
        filled the team, otherwise None (a join records no completion).
        """
        size = self.teamwork_size(chore)
        day = dt_util.as_local(now).date().isoformat()
        # A child deleted since joining can't be paid, so they stop counting.
        joined = [j for j in self.storage.get_team_joins(chore.id, day) if self.get_child(j["child_id"])]
        if any(j["child_id"] == child.id for j in joined):
            _LOGGER.debug("complete_chore no-op: %s already joined team chore '%s'", child.name, chore.name)
            return None

        entry = {"child_id": child.id, "joined_at": now.isoformat()}
        if photo_url:
            entry["photo_url"] = photo_url
        joined.append(entry)

        if len(joined) < size:
            self.storage.set_team_joins(chore.id, day, joined)
            self.hass.bus.async_fire(
                "taskmate_team_chore_joined",
                {
                    "child_id": child.id,
                    "child_name": child.name,
                    "chore_id": chore.id,
                    "chore_name": chore.name,
                    "joined": len(joined),
                    "team_size": size,
                },
            )
            await self.storage.async_save()
            await self.async_refresh()
            return None

        # Full. Clear the occurrence before anything can suspend, so a join
        # racing this one starts a fresh team instead of joining a spent one.
        self.storage.set_team_joins(chore.id, day, [])

        # The team submits through the chore's normal approval rules. A parent
        # completing on behalf is the approver (as for any chore), so when a
        # parent's tap is the one that fills the team, the whole team is
        # approved on the spot.
        requires_photo = bool(getattr(chore, "require_photo", False))
        auto_approve = as_parent or (not chore.requires_approval and not requires_photo)
        base = self.team_share_points(chore)

        recorded = []
        own = None
        for j in joined:
            member = self.get_child(j["child_id"])
            if member is None:
                continue
            points = self._apply_roulette_multiplier(
                chore,
                member.id,
                self._apply_speed_bonus(chore, self._apply_time_adjustment(chore, base, now), now),
            )
            completion = await self._async_record_completion(
                chore,
                member,
                now,
                auto_approve=auto_approve,
                points=points,
                # A parent's tap filling the team counts as made on everyone's
                # behalf, so it isn't child-undoable (#918); otherwise each
                # child may take back their own share within the window.
                as_parent=as_parent,
                photo_url=j.get("photo_url", ""),
            )
            recorded.append((member, completion, points))
            if member.id == child.id:
                own = completion

        self.hass.bus.async_fire(
            "taskmate_team_chore_completed",
            {
                "chore_id": chore.id,
                "chore_name": chore.name,
                "child_ids": [m.id for m, _c, _p in recorded],
                "team_size": size,
            },
        )
        await self._async_after_completions(chore, recorded, auto_approve=auto_approve)
        return own

    async def async_leave_team_chore(self, chore_id: str, child_id: str) -> bool:
        """Take ``child_id`` back out of today's team before it completes.

        Returns False (a soft no-op) when they hadn't joined — including when
        the team already completed, since that clears the joins. Only unknown
        ids raise.
        """
        chore = self.get_chore(chore_id)
        if not chore:
            raise ValueError(f"Chore {chore_id} not found")
        if not self.get_child(child_id):
            raise ValueError(f"Child {child_id} not found")
        if not self.teamwork_size(chore):
            raise ValueError(f"Chore '{chore.name}' is not a teamwork chore")

        day = dt_util.as_local(dt_util.now()).date().isoformat()
        joined = self.storage.get_team_joins(chore_id, day)
        kept = [j for j in joined if j["child_id"] != child_id]
        if len(kept) == len(joined):
            return False
        self.storage.set_team_joins(chore_id, day, kept)
        await self.storage.async_save()
        await self.async_refresh()
        return True
