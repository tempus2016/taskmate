# TaskMate automation blueprints

Ready-made [Home Assistant automation blueprints](https://www.home-assistant.io/docs/automation/using_blueprints/)
that react to TaskMate events. Each one fires on a TaskMate bus event and lets
you pick the action to run (flash a light, play a sound, send a notification,
run a scene…).

| Blueprint | Fires on event | Use it for |
|-----------|----------------|------------|
| `chore_completed.yaml` | `taskmate_chore_completed` | Flash a light / play a sound when a child completes a chore |
| `level_up.yaml` | `taskmate_level_up` | Celebrate a new XP level |
| `reward_approved.yaml` | `taskmate_reward_approved` | Announce / unlock something when a reward is approved |
| `mandatory_missed.yaml` | `taskmate_mandatory_missed` | React when a mandatory chore's window closes incomplete |

## Importing

In Home Assistant: **Settings → Automations & scenes → Blueprints → Import
blueprint**, then paste the raw URL of the blueprint, e.g.

```
https://github.com/tempus2016/taskmate/blob/main/blueprints/automation/taskmate/chore_completed.yaml
```

Then **Create automation → choose the imported blueprint**, optionally restrict
it to a single child by name, and pick your action.

## Event data available to your action

The triggering event is available in templates as `trigger.event.data`:

- `chore_completed` → `child_name`, `chore_name`, `points`, `difficulty`
- `level_up` → `child_name`, `level`
- `reward_approved` → `child_name`, `reward_name`, `cost`
- `mandatory_missed` → `child_id`, `chore_id`, `period_id`, `penalty_points`

Example action snippet using event data:

```yaml
service: notify.mobile_app_phone
data:
  message: "{{ trigger.event.data.child_name }} finished {{ trigger.event.data.chore_name }}!"
```
