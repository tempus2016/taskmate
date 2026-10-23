# Completion Heatmap

A calendar grid for each child: one square a day, darker green for busier days. It's on the panel's **Insights** page and on a dashboard card.

---

## Insights → Calendar

**TaskMate panel → Insights → Calendar** shows every child's grid for the last 4, 6 or 12 weeks, in Monday-first weeks. Hover a square for the date and the number of chores done. Each child's line also says how many chores they did and on how many of the days.

---

## Heatmap Card

```yaml
type: custom:taskmate-heatmap-card
entity: sensor.taskmate_overview
child_id: a8c8376a            # optional — leave out to show every child
title: My chore calendar      # optional — default: Chore calendar
header_color: "#2e7d32"
```

- The last six weeks, ending today (today has an outline)
- The visual editor has a child picker, the title, the [design style](Card-Design-Styles.md) and the header colour
- [Adults](Adult-Profiles.md) are left out unless `show_adults: true`

---

## What Counts

Every chore a child did on the day, approved or still waiting for a parent. Bonus sub-tasks and jobs a parent marked done themselves aren't counted. The shade is relative to that child's busiest day in the window, so a child who does two chores a day still gets dark squares.

The card reads `completion_heatmap` from the activity sensor: `{"end": "YYYY-MM-DD", "children": {child_id: [count, ...]}}`, 42 days oldest first. Children with nothing in the window are left out. The panel uses the `taskmate/reports/heatmap` WebSocket command (`days` 7–120, default 42).

---

## Related

- [Insights](Insights.md) — the other reports
- [Dashboard Cards](Dashboard-Cards.md#heatmap-card)
