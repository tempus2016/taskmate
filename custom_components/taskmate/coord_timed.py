"""Timed task operations mixin for TaskMateCoordinator."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.util import dt as dt_util

from .models import ChoreCompletion, TimedSession

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


class TimedMixin:
    """Mixin providing timed task start/pause/stop and session management."""

    async def async_start_timed_task(self, chore_id: str, child_id: str) -> None:
        """Start or resume a timed task session."""
        chore = self.get_chore(chore_id)
        if not chore:
            raise ValueError(f"Chore {chore_id} not found")
        if chore.task_type != "timed":
            raise ValueError(f"Chore '{chore.name}' is not a timed task")

        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        now = dt_util.now()
        today = dt_util.as_local(now).date().isoformat()

        existing = self.storage.get_active_timed_session(chore_id, child_id)
        if existing and existing.state == "running":
            raise ValueError("Timer is already running")

        if existing and existing.state == "paused":
            # Check daily cap before resuming
            if chore.timed_max_daily_minutes > 0:
                if existing.total_seconds_today >= chore.timed_max_daily_minutes * 60:
                    raise ValueError(
                        f"Daily cap reached ({chore.timed_max_daily_minutes} min)"
                    )
            existing.state = "running"
            existing.segments.append({"start": now.isoformat(), "end": None})
            self.storage.save_timed_session(existing)
        else:
            # Check daily cap before starting fresh
            if chore.timed_max_daily_minutes > 0:
                old_session = self.storage.get_timed_session(chore_id, child_id, today)
                if old_session and old_session.total_seconds_today >= chore.timed_max_daily_minutes * 60:
                    raise ValueError(
                        f"Daily cap reached ({chore.timed_max_daily_minutes} min)"
                    )
            session = TimedSession(
                chore_id=chore_id,
                child_id=child_id,
                state="running",
                segments=[{"start": now.isoformat(), "end": None}],
                total_seconds_today=0,
                session_date=today,
            )
            self.storage.save_timed_session(session)

        await self.storage.async_save()
        await self.async_refresh()

    async def async_pause_timed_task(self, chore_id: str, child_id: str) -> None:
        """Pause a running timed task session."""
        session = self.storage.get_active_timed_session(chore_id, child_id)
        if not session or session.state != "running":
            raise ValueError("No running timer to pause")

        now = dt_util.now()
        if session.segments and session.segments[-1].get("end") is None:
            session.segments[-1]["end"] = now.isoformat()

        session.total_seconds_today = self._calc_session_seconds(session)
        session.state = "paused"
        self.storage.save_timed_session(session)
        await self.storage.async_save()
        await self.async_refresh()

    async def async_stop_timed_task(self, chore_id: str, child_id: str) -> None:
        """Stop a timed task session and create a completion."""
        session = self.storage.get_active_timed_session(chore_id, child_id)
        if not session:
            raise ValueError("No active timer to stop")

        chore = self.get_chore(chore_id)
        if not chore:
            raise ValueError(f"Chore {chore_id} not found")

        child = self.get_child(child_id)
        if not child:
            raise ValueError(f"Child {child_id} not found")

        now = dt_util.now()

        # Close running segment
        if session.state == "running" and session.segments and session.segments[-1].get("end") is None:
            session.segments[-1]["end"] = now.isoformat()

        total_seconds = self._calc_session_seconds(session)

        # Clamp to daily cap
        if chore.timed_max_daily_minutes > 0:
            max_seconds = chore.timed_max_daily_minutes * 60
            total_seconds = min(total_seconds, max_seconds)

        # Calculate points. Guard against a mis-configured zero rate, which
        # would otherwise raise ZeroDivisionError and wedge the session.
        rate_seconds = chore.timed_rate_minutes * 60
        pts = (total_seconds // rate_seconds) * chore.timed_rate_points if rate_seconds > 0 else 0

        completion = ChoreCompletion(
            chore_id=chore_id,
            child_id=child_id,
            completed_at=now,
            approved=not chore.requires_approval,
            points_awarded=pts if not chore.requires_approval else 0,
            timed_duration_seconds=total_seconds,
        )

        if not chore.requires_approval:
            total_awarded = await self._award_points(child, pts)
            completion.approved = True
            completion.approved_at = dt_util.now()
            completion.points_awarded = total_awarded

        self.storage.add_completion(completion)
        self.storage.set_last_completed(chore_id, child_id, now.isoformat())
        self.storage.remove_timed_session(session.id)

        await self.storage.async_save()

        if chore.requires_approval:
            await self._async_notify_pending_approval(
                child.name, chore.name, pts, completion_id=completion.id,
            )

        await self.async_refresh()

    def _calc_session_seconds(self, session: TimedSession) -> int:
        """Calculate total elapsed seconds from session segments."""
        total = 0
        for seg in session.segments:
            start_str = seg.get("start")
            end_str = seg.get("end")
            if not start_str:
                continue
            try:
                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str) if end_str else dt_util.now()
                diff = (end_dt - start_dt).total_seconds()
                if diff > 0:
                    total += int(diff)
            except (ValueError, TypeError):
                continue
        return total

    async def _async_stop_stale_timed_sessions(self) -> None:
        """Auto-stop any timed sessions from a previous day (midnight cleanup)."""
        today = dt_util.as_local(dt_util.now()).date().isoformat()
        sessions = self.storage.get_timed_sessions()
        stale = [s for s in sessions if s.session_date != today and s.state in ("running", "paused")]

        for session in stale:
            chore = self.get_chore(session.chore_id)
            child = self.get_child(session.child_id)
            if not chore or not child:
                self.storage.remove_timed_session(session.id)
                continue

            # Close any open segment at midnight (tz-aware so it can be
            # subtracted from the tz-aware segment start)
            if session.segments and session.segments[-1].get("end") is None:
                midnight = dt_util.start_of_local_day()
                session.segments[-1]["end"] = midnight.isoformat()

            total_seconds = self._calc_session_seconds(session)
            if chore.timed_max_daily_minutes > 0:
                total_seconds = min(total_seconds, chore.timed_max_daily_minutes * 60)

            rate_seconds = chore.timed_rate_minutes * 60
            pts = (total_seconds // rate_seconds) * chore.timed_rate_points if rate_seconds > 0 else 0

            if total_seconds > 0:
                completion = ChoreCompletion(
                    chore_id=session.chore_id,
                    child_id=session.child_id,
                    completed_at=dt_util.now(),
                    approved=not chore.requires_approval,
                    points_awarded=pts if not chore.requires_approval else 0,
                    timed_duration_seconds=total_seconds,
                )
                if not chore.requires_approval:
                    total_awarded = await self._award_points(child, pts)
                    completion.approved = True
                    completion.approved_at = dt_util.now()
                    completion.points_awarded = total_awarded
                self.storage.add_completion(completion)

            self.storage.remove_timed_session(session.id)

        if stale:
            await self.storage.async_save()
            await self.async_refresh()

    async def _async_auto_stop_capped_sessions(self) -> None:
        """Check running sessions against daily cap and auto-stop if exceeded."""
        sessions = self.storage.get_timed_sessions()
        for session in sessions:
            if session.state != "running":
                continue
            chore = self.get_chore(session.chore_id)
            if not chore or chore.timed_max_daily_minutes <= 0:
                continue
            elapsed = self._calc_session_seconds(session)
            if elapsed >= chore.timed_max_daily_minutes * 60:
                await self.async_stop_timed_task(session.chore_id, session.child_id)
