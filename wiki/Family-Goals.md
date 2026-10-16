# Family Goals

A Family Goal is a single shared target the whole family works toward together. Instead of each child chasing their own rewards, everyone's points are added up against one combined target — *"when the family reaches 500 points between us, we have a movie night"*. It is co-operative rather than competitive, and it is **parent-controlled**.

![The Family Goal card](images/card-family-goal.png)

Where [Pool Mode](Pool-Mode-(Savings-Jars).md) lets a group of children save toward one reward jar, a Family Goal measures **everyone's combined balance** family-wide, with no deposits to make — it simply tracks the total.

Family Goals are **opt-in** and configured in the **TaskMate** panel → **Settings**, in the **Family goal** section of the Admin Panel.

---

## Settings

| Setting | Key | Default | Description |
|---------|-----|---------|-------------|
| **Enable family goal** | `family_goal_enabled` | `off` | Master toggle |
| **Goal name** | `family_goal_name` | *(blank)* | A friendly name, e.g. *Movie night fund* (up to 120 characters) |
| **Target (combined points)** | `family_goal_target` | `500` | Sum of all children's points needed to reach the goal (1–10,000,000) |
| **Reward** | `family_goal_reward` | *(blank)* | What the family gets, e.g. *a family movie night* (up to 200 characters) |

---

## Setting it up

1. Open the **Admin Panel** and scroll to the **Family goal** section
2. Switch **Enable family goal** on
3. Give it a **Goal name** — this is the headline shown on the card
4. Set a **Target** — the combined point total to aim for
5. Describe the **Reward** the family earns when the goal is reached

The progress metric is simply the **sum of every child's current points**. As children earn (and spend) points, the family total moves up and down toward the target.

If you change the **target** or toggle the goal off and on again, the "reached" state resets so the goal can be celebrated afresh.

---

## Reaching the goal

When the combined total first reaches the target, TaskMate fires a one-time **Family goal reached** notification announcing the goal name and its reward. The notification fires **once** per goal — it won't nag every time the total wobbles back above the line. (See [Notifications](Notifications.md) to control where it is delivered.)

A `taskmate_family_goal_reached` event is also fired with the goal name, reward, and target, so you can trigger your own celebration automation.

---

## The Family Goal card

Add the **Family Goal card** to a dashboard to show live progress toward the target — a progress bar, the combined total against the target, the percentage, and the reward. When the goal is reached the card switches to a trophy and a celebration message.

```yaml
type: custom:taskmate-family-goal-card
entity: sensor.taskmate_overview
title: Movie Night Fund
header_color: "#16a085"
```

| Option | Required | Description |
|--------|----------|-------------|
| `entity` | ✅ | The TaskMate overview sensor (`sensor.taskmate_overview`) |
| `title` | — | Overrides the heading; defaults to the goal name |
| `header_color` | — | Accent colour for the icon and progress bar (default `#16a085`) |

If no family goal is enabled, the card shows a quiet "No family goal set" placeholder. The card reads the overview sensor's `family_goal` attribute, which exposes `enabled`, `name`, `target`, `reward`, `progress`, and `achieved`.

See [Dashboard Cards](Dashboard-Cards.md) for the full set of cards.

---

## Related

- [Pool Mode (Savings Jars)](Pool-Mode-(Savings-Jars).md) — per-reward shared savings jars
- [Dashboard Cards](Dashboard-Cards.md) — adding the Family Goal card
- [Notifications](Notifications.md) — controlling the goal-reached notification
- [Sensor Attributes](Sensor-Attributes.md) — the `family_goal` overview attribute
