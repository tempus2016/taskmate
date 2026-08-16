"""Parent-facing insight reports (#679).

Reports answer questions the raw data doesn't: *am I dumping everything on the
eldest?* They are computed on demand rather than stored — they are derived
views over completions, and a stale cached report is worse than a slow one.

Fairness is the first; the shared window/aggregation helpers here are meant to
carry the friction and projection reports too.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

from .const import RECURRENCE_PERIOD_DAYS

_LOGGER = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 7
FRICTION_WINDOW_DAYS = 30
PROJECTION_DAYS = 7
MAX_PROJECTION_DAYS = 28
MAX_WINDOW_DAYS = 90

# A child's share of the family workload may sit this many percentage points
# either side of an even split before it's called out. Wide enough that normal
# week-to-week variation doesn't trigger it; narrow enough to catch a genuine
# imbalance. With two children an even split is 50%, so this flags at 65/35.
FAIR_SHARE_TOLERANCE = 15.0

# A chore completed on fewer than this fraction of the days it came up is
# "struggling"; below the dead threshold it is barely happening at all.
FRICTION_STRUGGLING_RATE = 0.6
FRICTION_DEAD_RATE = 0.2


class ReportsMixin:
    """Mixin providing on-demand parent insight reports."""

    def _report_window(self, days: int | None) -> tuple[date, date, int]:
        """Clamp the requested window and return (start, end, days) inclusive."""
        # `None` means "unspecified"; any supplied value is clamped. Using
        # truthiness here would silently turn a supplied 0 into the default
        # rather than the 1-day window the caller half-asked for.
        if days is None:
            span = DEFAULT_WINDOW_DAYS
        else:
            try:
                span = int(days)
            except (TypeError, ValueError):
                span = DEFAULT_WINDOW_DAYS
        span = max(1, min(span, MAX_WINDOW_DAYS))
        end = dt_util.as_local(dt_util.now()).date()
        return end - timedelta(days=span - 1), end, span

    def _completions_in_window(self, start: date, end: date) -> list:
        """Approved, non-bonus completions inside the window.

        Bonus sub-tasks are excluded: they're extra credit attached to a chore
        that's already counted, so including them would double-count the effort.
        Pending completions are excluded too — unapproved work isn't yet work
        the parent has agreed happened.
        """
        out = []
        for comp in self.storage.get_completions():
            if not getattr(comp, "approved", False):
                continue
            if getattr(comp, "bonus_subtask_id", ""):
                continue
            try:
                when = dt_util.as_local(comp.completed_at).date()
            except (AttributeError, TypeError, ValueError):
                continue
            if start <= when <= end:
                out.append(comp)
        return out

    def fairness_report(self, days: int | None = None) -> dict[str, Any]:
        """Who is actually doing the work, and is it evenly split?

        Reports both a chore count and a points total because they can
        disagree: one child doing three quick jobs and another doing one hard
        one is balanced by points and lopsided by count. Showing both lets the
        parent decide which they meant.
        """
        start, end, span = self._report_window(days)
        children = self.storage.get_children()
        completions = self._completions_in_window(start, end)

        by_child: dict[str, dict[str, Any]] = {
            c.id: {"id": c.id, "name": c.name, "completions": 0, "points": 0, "active_days": set()} for c in children
        }
        for comp in completions:
            entry = by_child.get(comp.child_id)
            if entry is None:
                continue  # a since-deleted child's history
            entry["completions"] += 1
            entry["points"] += int(getattr(comp, "points_awarded", 0) or 0)
            entry["active_days"].add(dt_util.as_local(comp.completed_at).date().isoformat())

        total_completions = sum(e["completions"] for e in by_child.values())
        total_points = sum(e["points"] for e in by_child.values())
        fair_share = 100.0 / len(children) if children else 0.0

        rows = []
        for entry in by_child.values():
            share_completions = entry["completions"] / total_completions * 100 if total_completions else 0.0
            share_points = entry["points"] / total_points * 100 if total_points else 0.0
            # Judge on chore count: it's the closest proxy for "how much did
            # they actually have to do", independent of how a chore is priced.
            delta = share_completions - fair_share
            if not total_completions:
                status = "idle"
            elif delta > FAIR_SHARE_TOLERANCE:
                status = "over"
            elif delta < -FAIR_SHARE_TOLERANCE:
                status = "under"
            else:
                status = "balanced"
            rows.append(
                {
                    "id": entry["id"],
                    "name": entry["name"],
                    "completions": entry["completions"],
                    "points": entry["points"],
                    "share_completions": round(share_completions, 1),
                    "share_points": round(share_points, 1),
                    "delta": round(delta, 1),
                    "active_days": len(entry["active_days"]),
                    "status": status,
                }
            )

        rows.sort(key=lambda r: (-r["completions"], r["name"]))
        return {
            "days": span,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "generated_at": dt_util.now().isoformat(),
            "fair_share": round(fair_share, 1),
            "tolerance": FAIR_SHARE_TOLERANCE,
            "total_completions": total_completions,
            "total_points": total_points,
            "children": rows,
            "balanced": all(r["status"] in ("balanced", "idle") for r in rows),
        }

    # ── Friction (#680) ──────────────────────────────────────────────────

    def _expected_occurrences(self, chore, start: date, end: date) -> int:
        """Roughly how many times this chore should have come up in the window.

        An approximation on purpose: the exact answer would need to replay
        rotation, dependencies, weather and vacation for every day, and the
        report only needs "often enough to judge a rate by".
        """
        mode = getattr(chore, "schedule_mode", "specific_days")
        span = (end - start).days + 1

        if mode == "one_shot":
            return 1

        if mode == "recurring":
            period_days = RECURRENCE_PERIOD_DAYS.get(getattr(chore, "recurrence", "weekly"), 7)
            return max(0, span // period_days)

        due_days = [d.lower() for d in (getattr(chore, "due_days", []) or [])]
        if not due_days:
            return span  # no restriction = every day
        wanted = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        targets = {wanted[d] for d in due_days if d in wanted}
        if not targets:
            return span
        return sum(1 for i in range(span) if (start + timedelta(days=i)).weekday() in targets)

    def friction_report(self, days: int | None = None) -> dict[str, Any]:
        """Which chores are not working, and what to do about them.

        Note on what is NOT here: TaskMate deletes a completion when a parent
        rejects it, and removes a mandatory miss once it is resolved, so
        neither rejection counts nor historical miss counts can be derived.
        The report is built from what is actually retained — completion
        history, the last-completed store, and currently outstanding misses.
        """
        start, end, span = self._report_window(days or FRICTION_WINDOW_DAYS)
        today = end
        completions = self._completions_in_window(start, end)

        done_by_chore: dict[str, int] = {}
        for comp in completions:
            done_by_chore[comp.chore_id] = done_by_chore.get(comp.chore_id, 0) + 1

        # Outstanding mandatory misses, and how hard each had to be chased.
        misses_by_chore: dict[str, int] = {}
        chased_by_chore: dict[str, int] = {}
        for miss in self.storage.get_mandatory_misses():
            misses_by_chore[miss.chore_id] = misses_by_chore.get(miss.chore_id, 0) + 1
            if int(getattr(miss, "escalation_stage", 0) or 0) >= 2:
                chased_by_chore[miss.chore_id] = chased_by_chore.get(miss.chore_id, 0) + 1

        rows = []
        for chore in self.storage.get_chores():
            if not getattr(chore, "enabled", True):
                continue

            done = done_by_chore.get(chore.id, 0)
            expected = self._expected_occurrences(chore, start, end)
            rate = (done / expected) if expected else None

            last_done = self._last_completed_date(chore.id)
            days_since = (today - last_done).days if last_done else None

            if last_done is None:
                verdict = "never"
            elif rate is None:
                verdict = "unknown"
            elif rate >= FRICTION_STRUGGLING_RATE:
                verdict = "fine"
            elif rate >= FRICTION_DEAD_RATE:
                verdict = "struggling"
            else:
                verdict = "stalling"

            rows.append(
                {
                    "id": chore.id,
                    "name": chore.name,
                    "points": int(getattr(chore, "points", 0) or 0),
                    "completed": done,
                    "expected": expected,
                    "rate": round(rate * 100, 1) if rate is not None else None,
                    "days_since": days_since,
                    "last_done": last_done.isoformat() if last_done else None,
                    "outstanding_misses": misses_by_chore.get(chore.id, 0),
                    "needed_chasing": chased_by_chore.get(chore.id, 0),
                    "verdict": verdict,
                    "suggestion": self._friction_suggestion(verdict, days_since, chore),
                }
            )

        # Worst first: never done, then lowest completion rate.
        order = {"never": 0, "stalling": 1, "struggling": 2, "unknown": 3, "fine": 4}
        rows.sort(key=lambda r: (order.get(r["verdict"], 9), r["rate"] if r["rate"] is not None else 0, r["name"]))
        return {
            "days": span,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "generated_at": dt_util.now().isoformat(),
            "chores": rows,
            "problem_count": sum(1 for r in rows if r["verdict"] in ("never", "stalling")),
            # Surfaced so the UI can say why rejections aren't listed rather
            # than leaving the parent wondering.
            "tracks_rejections": False,
        }

    def _last_completed_date(self, chore_id: str) -> date | None:
        """Most recent completion of a chore by anyone, from the fast store.

        Reads last_completed rather than scanning history so a chore last done
        long before the window still reports honestly instead of "never".
        """
        record = self.storage.data.get("last_completed", {}).get(chore_id, {})
        latest: date | None = None
        for per_child in (record or {}).values():
            stamp = (per_child or {}).get("current")
            if not stamp:
                continue
            try:
                when = dt_util.as_local(datetime.fromisoformat(stamp)).date()
            except (TypeError, ValueError):
                continue
            if latest is None or when > latest:
                latest = when
        return latest

    @staticmethod
    def _friction_suggestion(verdict: str, days_since: int | None, chore) -> str:
        """A concrete next step, not just a diagnosis."""
        if verdict == "never":
            return "retire"
        if verdict == "stalling":
            # Long dead vs merely unpopular need different answers.
            if days_since is not None and days_since > 30:
                return "retire"
            return "reprice" if int(getattr(chore, "points", 0) or 0) <= 5 else "reassign"
        if verdict == "struggling":
            return "reprice"
        return "keep"

    # ── Projection (#681) ────────────────────────────────────────────────

    def _chore_falls_on(self, chore, day: date) -> bool:
        """Would this chore come up on ``day`` under its schedule alone?

        Schedule only. Entity-driven gates (weather, visibility, availability)
        are current-state facts that can't be known for a future date, so the
        projection is explicitly "what the calendar says", not a promise.
        """
        mode = getattr(chore, "schedule_mode", "specific_days")
        if mode == "one_shot":
            created = getattr(chore, "created_date", "")
            try:
                return bool(created) and date.fromisoformat(created) == day
            except (TypeError, ValueError):
                return False

        expires = getattr(chore, "expires_on", "")
        if expires:
            try:
                if day > date.fromisoformat(expires):
                    return False
            except (TypeError, ValueError):
                pass

        if mode == "recurring":
            period_days = RECURRENCE_PERIOD_DAYS.get(getattr(chore, "recurrence", "weekly"), 7)
            anchor_raw = getattr(chore, "recurrence_start", "") or ""
            try:
                anchor = date.fromisoformat(anchor_raw) if anchor_raw else None
            except (TypeError, ValueError):
                anchor = None
            if anchor is None:
                # No anchor: fall back to the weekday, or treat weekly as "once
                # a week from today" so the projection isn't silently empty.
                wanted = (getattr(chore, "recurrence_day", "") or "").lower()
                if wanted:
                    return day.strftime("%A").lower() == wanted
                return ((day - dt_util.as_local(dt_util.now()).date()).days % period_days) == 0
            return ((day - anchor).days % period_days) == 0

        due_days = [d.lower() for d in (getattr(chore, "due_days", []) or [])]
        if not due_days:
            return True
        return day.strftime("%A").lower() in due_days

    def projection_report(self, days: int | None = None) -> dict[str, Any]:
        """What the week ahead looks like: who gets what, and worth how much.

        Rotation is projected with the coordinator's own daily-assignment
        computation per day, so alternating/random/balanced picks match what
        will really happen rather than an independent guess that could drift.
        """
        try:
            span = int(days) if days is not None else PROJECTION_DAYS
        except (TypeError, ValueError):
            span = PROJECTION_DAYS
        span = max(1, min(span, MAX_PROJECTION_DAYS))

        today = dt_util.as_local(dt_util.now()).date()
        children = self.storage.get_children()
        chores = [c for c in self.storage.get_chores() if getattr(c, "enabled", True)]

        totals = {c.id: {"id": c.id, "name": c.name, "points": 0, "chores": 0} for c in children}
        unassigned_points = 0
        day_rows = []

        for offset in range(span):
            day = today + timedelta(days=offset)
            daily_assignments = self._compute_daily_assignments(day)
            per_day = {c.id: {"points": 0, "chores": 0} for c in children}
            day_unassigned = 0

            for chore in chores:
                if not self._chore_falls_on(chore, day):
                    continue
                value = self.effective_chore_points(chore)
                mode = getattr(chore, "assignment_mode", "everyone")

                if mode in ("everyone", "first_come"):
                    # Anyone in the pool may do it; credit the pool rather than
                    # inventing a winner the schedule can't know.
                    pool = list(getattr(chore, "assigned_to", []) or []) or [c.id for c in children]
                    for child_id in pool:
                        if child_id in per_day:
                            per_day[child_id]["points"] += value
                            per_day[child_id]["chores"] += 1
                elif mode == "unassigned":
                    day_unassigned += value
                else:
                    child_id = daily_assignments.get(chore.id, "")
                    if child_id and child_id in per_day:
                        per_day[child_id]["points"] += value
                        per_day[child_id]["chores"] += 1
                    else:
                        day_unassigned += value

            for child_id, figures in per_day.items():
                totals[child_id]["points"] += figures["points"]
                totals[child_id]["chores"] += figures["chores"]
            unassigned_points += day_unassigned

            day_rows.append(
                {
                    "date": day.isoformat(),
                    "weekday": day.strftime("%A").lower(),
                    "children": [
                        {"id": cid, "points": f["points"], "chores": f["chores"]} for cid, f in per_day.items()
                    ],
                    "unassigned_points": day_unassigned,
                }
            )

        for child in children:
            entry = totals[child.id]
            entry["current_points"] = int(getattr(child, "points", 0) or 0)
            entry["projected_total"] = entry["current_points"] + entry["points"]

        return {
            "days": span,
            "start": today.isoformat(),
            "end": (today + timedelta(days=span - 1)).isoformat(),
            "generated_at": dt_util.now().isoformat(),
            "children": sorted(totals.values(), key=lambda r: (-r["points"], r["name"])),
            "by_day": day_rows,
            "unassigned_points": unassigned_points,
            # Shared-pool chores are credited to every eligible child, so the
            # per-child figures are a ceiling, not a forecast. Say so.
            "is_ceiling": True,
        }

    # ── Health & diagnostics (#682) ──────────────────────────────────────

    def health_report(self) -> dict[str, Any]:
        """Storage size, entity counts, and anything obviously wrong.

        Every issue carries a severity, a human sentence, and where to fix it.
        A diagnostic that only says "3 problems" is a diagnostic the parent
        can't act on.
        """
        import json

        data = self.storage.data
        children = self.storage.get_children()
        chores = self.storage.get_chores()
        rewards = self.storage.get_rewards()
        completions = self.storage.get_completions()

        child_ids = {c.id for c in children}
        chore_ids = {c.id for c in chores}

        issues: list[dict[str, Any]] = []

        def add(severity: str, code: str, message: str, where: str, count: int = 1) -> None:
            issues.append(
                {
                    "severity": severity,
                    "code": code,
                    "message": message,
                    "where": where,
                    "count": count,
                }
            )

        # ── orphaned references ──────────────────────────────────────────
        orphan_assignees = [
            c.name for c in chores if any(cid not in child_ids for cid in (getattr(c, "assigned_to", []) or []))
        ]
        if orphan_assignees:
            add(
                "warning",
                "chore_orphan_assignee",
                f"{len(orphan_assignees)} chore(s) are assigned to a child that no longer exists",
                "chores",
                len(orphan_assignees),
            )

        orphan_rewards = [
            r.name for r in rewards if any(cid not in child_ids for cid in (getattr(r, "assigned_to", []) or []))
        ]
        if orphan_rewards:
            add(
                "warning",
                "reward_orphan_assignee",
                f"{len(orphan_rewards)} reward(s) are assigned to a child that no longer exists",
                "rewards",
                len(orphan_rewards),
            )

        orphan_deps = [
            c.name for c in chores if any(dep not in chore_ids for dep in (getattr(c, "depends_on", []) or []))
        ]
        if orphan_deps:
            add(
                "error",
                "chore_orphan_dependency",
                f"{len(orphan_deps)} chore(s) depend on a chore that no longer exists, so they can never unlock",
                "chores",
                len(orphan_deps),
            )

        orphan_completions = sum(1 for c in completions if c.chore_id not in chore_ids or c.child_id not in child_ids)
        if orphan_completions:
            add(
                "info",
                "completion_orphan",
                f"{orphan_completions} completion record(s) refer to a deleted chore or child",
                "activity",
                orphan_completions,
            )

        # ── configuration that can't work ────────────────────────────────
        missing_entities = []
        for chore in chores:
            for field in ("visibility_entity", "weather_entity"):
                entity_id = (getattr(chore, field, "") or "").strip()
                if entity_id and self.hass.states.get(entity_id) is None:
                    missing_entities.append(f"{chore.name} → {entity_id}")
        if missing_entities:
            add(
                "warning",
                "chore_missing_entity",
                f"{len(missing_entities)} chore(s) reference an entity that doesn't exist",
                "chores",
                len(missing_entities),
            )

        unlock_offlist = [
            r.name
            for r in rewards
            if (getattr(r, "unlock_entity", "") or "") and not self.is_unlock_allowed(r.unlock_entity)
        ]
        if unlock_offlist:
            add(
                "warning",
                "reward_unlock_not_allowed",
                f"{len(unlock_offlist)} reward(s) unlock an entity that is no longer on the "
                "allowlist, so nothing will happen when they're approved",
                "settings",
                len(unlock_offlist),
            )

        no_chores = [c.name for c in children if not self._child_has_any_chore(c.id, chores)]
        if no_chores:
            add(
                "info",
                "child_without_chores",
                f"{len(no_chores)} child/children have no chores assigned to them",
                "children",
                len(no_chores),
            )

        # ── size ─────────────────────────────────────────────────────────
        try:
            storage_bytes = len(json.dumps(data, default=str).encode("utf-8"))
        except (TypeError, ValueError):
            storage_bytes = 0

        # The recorder refuses to store an attribute payload over 16KB, so a
        # large completion history is worth flagging before it bites.
        if len(completions) > 5000:
            add(
                "info",
                "large_history",
                f"{len(completions)} completion records stored; history pruning keeps "
                "this in check but a large history slows every report",
                "activity",
                len(completions),
            )

        severity_rank = {"error": 0, "warning": 1, "info": 2}
        issues.sort(key=lambda i: (severity_rank.get(i["severity"], 9), i["code"]))

        return {
            "generated_at": dt_util.now().isoformat(),
            "healthy": not any(i["severity"] in ("error", "warning") for i in issues),
            "issues": issues,
            "counts": {
                "children": len(children),
                "chores": len(chores),
                "enabled_chores": sum(1 for c in chores if getattr(c, "enabled", True)),
                "rewards": len(rewards),
                "completions": len(completions),
                "badges": len(self.storage.get_badges()),
                "scheduled_changes": len(self.storage.get_scheduled_changes()),
                "active_unlocks": len(self.active_unlocks()),
                "mandatory_misses": len(self.storage.get_mandatory_misses()),
            },
            "storage_bytes": storage_bytes,
            "data_version": self.storage.data_version,
        }

    @staticmethod
    def _child_has_any_chore(child_id: str, chores) -> bool:
        """True when any chore could reach this child.

        An empty assigned_to means "everyone", so it counts.
        """
        for chore in chores:
            if not getattr(chore, "enabled", True):
                continue
            assigned = getattr(chore, "assigned_to", []) or []
            if not assigned or child_id in assigned:
                return True
        return False
