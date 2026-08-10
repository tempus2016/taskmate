"""Printable weekly chore chart (#689).

Builds a self-contained HTML page sized for a sheet of paper, meant for the
fridge. Portrait or landscape is the parent's choice — a family with two
children and short chore names wants portrait; one with five children needs
the width.

Pure string building with no HA imports, so the layout is unit-testable
without a Home Assistant install.
"""

from __future__ import annotations

from datetime import date, timedelta
from html import escape

ORIENTATIONS = ("portrait", "landscape")
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def week_start(day: date, starts_on: str = "monday") -> date:
    """The first day of the week containing ``day``."""
    offset = day.weekday() if starts_on == "monday" else (day.weekday() + 1) % 7
    return day - timedelta(days=offset)


def _falls_on(chore: dict, day: date) -> bool:
    """Schedule-only: would this chore appear on ``day``?

    Deliberately ignores entity-driven gates. A paper chart can't know next
    Thursday's weather, and a chart that quietly omitted a chore would be
    worse than one that lists it.
    """
    if not chore.get("enabled", True):
        return False
    mode = chore.get("schedule_mode", "specific_days")
    if mode == "one_shot":
        return str(chore.get("created_date", "")) == day.isoformat()
    if mode == "recurring":
        return True  # shown every day; the exact window depends on completions
    due = [str(d).lower() for d in (chore.get("due_days") or [])]
    return not due or day.strftime("%A").lower() in due


def build_chart(
    children: list[dict],
    chores: list[dict],
    start: date,
    *,
    orientation: str = "portrait",
    title: str = "This week",
    points_name: str = "Stars",
) -> str:
    """Render the printable chart as a standalone HTML document."""
    if orientation not in ORIENTATIONS:
        orientation = "portrait"

    days = [start + timedelta(days=i) for i in range(7)]
    rows = []

    for child in children:
        child_id = str(child.get("id", ""))
        # A chore with an empty assigned_to belongs to everyone.
        mine = [c for c in chores if not (c.get("assigned_to") or []) or child_id in (c.get("assigned_to") or [])]
        if not mine:
            continue

        cells = []
        for day in days:
            todays = [c for c in mine if _falls_on(c, day)]
            boxes = "".join(
                f'<div class="task"><span class="tick"></span>'
                f'<span class="name">{escape(str(c.get("name", "")))}</span></div>'
                for c in todays
            )
            cells.append(f"<td>{boxes or '&nbsp;'}</td>")
        rows.append(f'<tr><th class="who">{escape(str(child.get("name", "")))}</th>' + "".join(cells) + "</tr>")

    header = "".join(
        f'<th><span class="dow">{DAY_NAMES[d.weekday()][:3]}</span><span class="dom">{d.day}</span></th>' for d in days
    )
    week_label = f"{start.strftime('%d %b')} – {(start + timedelta(days=6)).strftime('%d %b %Y')}"
    body = "".join(rows) or ('<tr><td colspan="8" class="empty">No chores to show for this week.</td></tr>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{escape(title)} — {escape(week_label)}</title>
<style>
  /* Sized for a sheet of paper, not a screen: the whole point is the fridge. */
  @page {{ size: A4 {orientation}; margin: 10mm; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 12px;
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    color: #000; background: #fff;
  }}
  header {{ display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 10px; }}
  h1 {{ font-size: 20px; margin: 0; }}
  .week {{ font-size: 13px; color: #333; }}
  table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
  th, td {{ border: 1.5px solid #000; vertical-align: top; padding: 5px; }}
  thead th {{ background: #eee; text-align: center; padding: 4px; }}
  .dow {{ display: block; font-size: 12px; font-weight: 800; text-transform: uppercase; }}
  .dom {{ display: block; font-size: 11px; color: #444; }}
  .who {{ width: 92px; background: #eee; font-size: 13px; text-align: left; }}
  .task {{ display: flex; align-items: flex-start; gap: 4px; margin-bottom: 3px; }}
  /* An empty box to tick with a pen — the entire reason this exists on paper. */
  .tick {{
    flex: 0 0 auto; width: 11px; height: 11px;
    border: 1.5px solid #000; border-radius: 2px; margin-top: 1px;
  }}
  .name {{ font-size: 10.5px; line-height: 1.25; }}
  .empty {{ text-align: center; padding: 24px; font-size: 13px; color: #444; }}
  footer {{ margin-top: 8px; font-size: 10px; color: #444; }}
  /* Never carry a browser's header/footer or a stray background into print. */
  @media print {{ body {{ padding: 0; }} .noprint {{ display: none; }} }}
</style>
</head>
<body>
<header>
  <h1>{escape(title)}</h1>
  <div class="week">{escape(week_label)}</div>
</header>
<table>
  <thead><tr><th class="who">&nbsp;</th>{header}</tr></thead>
  <tbody>{body}</tbody>
</table>
<footer>Tick each box as it's done. {escape(points_name)} are still awarded in TaskMate.</footer>
</body>
</html>"""
