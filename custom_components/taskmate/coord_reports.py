"""Parent-facing insight reports (#679).

Reports answer questions the raw data doesn't: *am I dumping everything on the
eldest?* They are computed on demand rather than stored — they are derived
views over completions, and a stale cached report is worse than a slow one.

Fairness is the first; the shared window/aggregation helpers here are meant to
carry the friction and projection reports too.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 7
MAX_WINDOW_DAYS = 90

# A child's share of the family workload may sit this many percentage points
# either side of an even split before it's called out. Wide enough that normal
# week-to-week variation doesn't trigger it; narrow enough to catch a genuine
# imbalance. With two children an even split is 50%, so this flags at 65/35.
FAIR_SHARE_TOLERANCE = 15.0


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
            c.id: {"id": c.id, "name": c.name, "completions": 0, "points": 0, "active_days": set()}
            for c in children
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
            share_completions = (
                entry["completions"] / total_completions * 100 if total_completions else 0.0
            )
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
            rows.append({
                "id": entry["id"],
                "name": entry["name"],
                "completions": entry["completions"],
                "points": entry["points"],
                "share_completions": round(share_completions, 1),
                "share_points": round(share_points, 1),
                "delta": round(delta, 1),
                "active_days": len(entry["active_days"]),
                "status": status,
            })

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
