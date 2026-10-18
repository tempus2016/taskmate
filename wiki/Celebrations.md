# Celebrations

Celebrations are the "big moment" layer of TaskMate. The notable things a child achieves — levelling up, hitting a streak milestone, finishing a quest, earning a perfect week — flow through one funnel that fires a single event carrying a **tier**, so a single automation can scale its reaction to the size of the moment. There's also an opt-in notification for the biggest moments.

![The Child card](images/card-child.png)

---

## What Triggers a Celebration

The following moments fire a celebration, each with a tier set by how big a deal it is:

| Moment | Tier | Notes |
|--------|------|-------|
| **Level up** | 2 (medium), or 3 (epic) on every 5th level | One per level crossed — see [Levels and XP](Levels-and-XP.md) |
| **Streak milestone** | 2 (medium), or 3 (epic) at 30+ days | See [Bonus Points](Bonus-Points.md) |
| **Perfect week** | 3 (epic) | See [Bonus Points](Bonus-Points.md) |
| **Quest completed** | 3 (epic) | See [Quests](Quests.md) |
| **Challenge completed** | 2 (medium) | See [Challenges](Challenges.md) |
| **Weekly target reached** | 2 (medium) | v6.2.0. Only on chores with a weekly target bonus. See [Weekly Targets](Weekly-Targets.md#weekly-target-bonus) |
| **Personal best** | 2 (medium) | v7.1.0. A child beat one of their own records. See [Personal Bests](Personal-Bests.md) |

---

## The Tiers

Every celebration carries a numeric tier so automations can react proportionally:

| Tier | Meaning |
|------|---------|
| `1` | Small |
| `2` | Medium |
| `3` | Epic |

---

## What Happens

### The `taskmate_celebration` event (always)

Every celebration fires a single `taskmate_celebration` bus event. This is the integration point for power users — wire it into automations to flash lights, play a sound, or speak a message, and use the `tier` to scale the reaction. The payload includes:

| Field | Description |
|-------|-------------|
| `child_id` | The child the celebration is for |
| `child_name` | The child's name |
| `kind` | The moment type: `level_up`, `streak_milestone`, `perfect_week`, `quest_completed`, `challenge_completed`, `weekly_target_reached`, `personal_best` |
| `tier` | `1` (small), `2` (medium), or `3` (epic) |
| `message` | A ready-made human-readable message |
| `timestamp` | ISO timestamp |

Some kinds add extras, e.g. `level`, `days`, `bonus`, `quest_id` / `challenge_id` / `chore_id`, or `record` / `value` / `previous` for a personal best, depending on the moment.

Since v6.2.0 the `message` is written in Home Assistant's language (**Settings → System → General**), so a TTS automation that speaks it talks in your language too. See [Localization](Localization.md#push-notifications).

### The celebration notification (opt-in)

In addition to the event, a celebration can send a **notification** through TaskMate's routing system. This is **off by default** and only fires for moments at or above your chosen minimum size — so you can be alerted to the big stuff without being pinged for every small win.

| Setting | Default | Description |
|---------|---------|-------------|
| **Celebration notifications** (`celebration_notify`) | off | Master toggle for the `celebration` notification |
| **Minimum celebration size** (`celebration_notify_min_tier`) | `2` (Medium and up) | Only notify for moments at or above this tier: `1` = All, `2` = Medium and up, `3` = Epic only |

Configure both in the **Admin Panel → Settings** tab. Notifications still route to whichever recipients you've enabled for the `celebration` type — see [Notifications](Notifications.md).

> The minimum-size setting only gates the **notification**. The `taskmate_celebration` event always fires for every celebration regardless of tier, so automations never miss a moment.

---

## On-screen Celebration (Child and Kiosk Cards)

Separately from the celebration funnel, the [child card](Dashboard-Cards.md) plays its own on-screen flourish — a confetti burst and a completion sound — when a child ticks off a chore, and a pop/shimmer highlight when they earn a badge. This is local card feedback for the child in front of the screen; it is driven by the card itself, not by the `taskmate_celebration` event.

When a tick-off reaches a chore's [weekly target](Weekly-Targets.md#weekly-target-bonus) on a chore that doesn't need approval, the popup adds **🎉 Weekly target reached! +N** (v6.2.0).

Since v6.2.0 the [Kiosk card](Kiosk-Mode.md#celebrations) gives the same feedback when a child taps **Done**: the chore's sound, confetti and the "AWESOME! You did it!" popup.

---

## Automation Example

### Scale the reaction to the tier

```yaml
alias: TaskMate celebrations
triggers:
  - trigger: event
    event_type: taskmate_celebration
actions:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ trigger.event.data.tier == 3 }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: light.living_room
            data:
              flash: long
              color_name: gold
          - action: tts.google_translate_say
            data:
              entity_id: media_player.kitchen_speaker
              message: "{{ trigger.event.data.message }}"
    default:
      - action: notify.family
        data:
          message: "{{ trigger.event.data.message }}"
```

---

## Related

- [Levels and XP](Levels-and-XP.md) — level-ups feed celebrations
- [Bonus Points](Bonus-Points.md) — streak milestones and perfect weeks
- [Quests](Quests.md) and [Challenges](Challenges.md) — completions fire celebrations
- [Notifications](Notifications.md) — routing for the `celebration` notification type
- [Dashboard Cards](Dashboard-Cards.md) — the child card's on-screen confetti
- [Kiosk Mode](Kiosk-Mode.md) — the same celebrations on a shared tablet
- [Weekly Targets](Weekly-Targets.md) — the weekly target bonus
- [Completion Sounds](Completion-Sounds.md) — the per-chore sound played on a tick-off
