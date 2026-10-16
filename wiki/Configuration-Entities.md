# Configuration Entities

A handful of TaskMate's most useful settings are also exposed as standard Home Assistant **number** and **select** entities. This lets you read or change them straight from the HA UI, or from an automation or script, without going through the [Admin Panel](Admin-Panel.md) or a service call.

![The Settings tab](images/panel-settings.png)

These entities and the Admin Panel are two views of the **same** stored settings — change one and the other updates to match.

---

## Number Entities

| Entity | Friendly name | Range | Step | Default | Controls |
|--------|---------------|-------|------|---------|----------|
| `number.taskmate_weekend_multiplier` | Weekend multiplier | 1.0–5.0 | 0.5 | 2.0 | Multiplier applied to chore points on Saturday and Sunday. Set `1.0` to disable. See [Bonus Points](Bonus-Points.md). |
| `number.taskmate_perfect_week_bonus` | Perfect week bonus | 0–1000 | 1 | 50 | Points awarded to a child who completes at least one chore every day Mon–Sun. See [Bonus Points](Bonus-Points.md). |

---

## Select Entities

| Entity | Friendly name | Options | Default | Controls |
|--------|---------------|---------|---------|----------|
| `select.taskmate_streak_reset_mode` | Streak reset mode | `reset`, `pause` | `reset` | What happens when a child misses a day. **reset**: the streak goes back to 0. **pause**: the streak freezes and resumes on the next completion. |
| `select.taskmate_card_design` | Card design | `classic`, `playroom`, `console`, `cleanpro`, `accessible` | `classic` | The global default visual style for TaskMate cards. See [Card Design Styles](Card-Design-Styles.md). |

The entity IDs above use each setting's translation key. If you've renamed entities in Home Assistant, your IDs may differ — look them up under **Settings → Devices & services → Entities** and filter by the **TaskMate** device.

---

## Changing Them

### From the UI

Add the entities to a dashboard (for example with an Entities card) and adjust them directly — slide the number, or pick from the dropdown. Changes save immediately and are reflected in the Admin Panel settings.

### From an automation

Because they're ordinary entities, you can drive them from automations. For example, raise the weekend multiplier during a school-holiday week:

```yaml
alias: TaskMate — Holiday week double points
triggers:
  - trigger: state
    entity_id: calendar.school_holidays
    to: "on"
actions:
  - action: number.set_value
    target:
      entity_id: number.taskmate_weekend_multiplier
    data:
      value: 2.0
```

Or switch every card to the playroom style for younger users:

```yaml
actions:
  - action: select.select_option
    target:
      entity_id: select.taskmate_card_design
    data:
      option: playroom
```

---

## See Also

- [Settings](Settings.md) — the full settings reference (these entities mirror a subset of it)
- [Bonus Points](Bonus-Points.md) — weekend multiplier and perfect-week bonus in detail
- [Card Design Styles](Card-Design-Styles.md) — the available card styles
