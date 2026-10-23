# Shopping-List Jobs

Add **"#tm fetch logs from the shed"** to Home Assistant's shopping list — or say it to Assist — and a couple of minutes later the children see **🛒 Fetch logs from the shed**. When the job is done, TaskMate ticks the item off the list.

---

## Setting It Up

**Settings → Shopping-list jobs** in the TaskMate panel.

| Setting | What it does |
|---------|--------------|
| **Turn on shopping-list jobs** | Off by default |
| **To-do list** | Any `todo` entity. Default `todo.shopping_list` |
| **Tag** | Only items that **start** with this become jobs. Default `#tm`, no spaces |
| **Points per job** | Default 5 |
| **Who does it** | **First to do it** — every chosen child sees it and the first to finish gets the points; or **Take turns** — one child per job, going round the chosen children |
| **Children** | None chosen means every child who isn't an adult |

---

## How It Works

- TaskMate reads the list's open items every two minutes (`todo.get_items`).
- An item counts when its text starts with the tag, followed by a space, `:` or `-`. `#tm sweep the path` and `#TM: sweep the path` both work; `#tmp…` and `sweep the path #tm` don't. The job is named after the rest of the text, with its first letter in capitals.
- Each item becomes **one** job, matched by the to-do item's id, however often the list is read.
- The job is a one-off chore with no deadline. While the item is still on the list and nobody has done it, the job carries over from day to day.
- **Done:** once the chore is completed — and approved, if it needs approval — TaskMate marks the item completed with `todo.update_item`.
- **Ticked off or deleted first:** the job is removed if nobody has done it. If a child already did it, it stays for a parent to approve or reject.
- If the list can't be read (the entity is missing or unavailable), nothing is removed.
- Deleting the job in TaskMate leaves the item on the list, and it won't come back as a job.

---

## Automations

### Event

| Event | Fields |
|-------|--------|
| `taskmate_shopping_job` | `kind` (`added` / `done` / `removed`), `chore_id`, `chore_name`, `item_uid`, `child_ids`, `timestamp` |

It also shows on the family [event entity](Event-Entities.md) as *Shopping-list job*.

```yaml
# Tell the kids when a new job lands
triggers:
  - trigger: event
    event_type: taskmate_shopping_job
    event_data:
      kind: added
actions:
  - action: notify.family_tablet
    data:
      message: "New job: {{ trigger.event.data.chore_name }}"
```

---

## Related

- [Bin-Day Chores](Bin-Day-Chores.md) — chores raised from a calendar
- [To-Do Lists](To-Do-Lists.md) — TaskMate's own to-do list entities
- [Reactive Chores](Reactive-Chores.md)
