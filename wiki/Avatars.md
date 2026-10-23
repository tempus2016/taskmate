# Avatars

Avatars are unlockable character icons children earn by hitting milestones. Each avatar is gated behind a requirement — a level, a lifetime-points total, or a best-streak length — giving kids something extra to work toward. Once unlocked, a child can switch to it themselves.

![A child's avatar on the Child card](images/card-child.png)

This page covers the **unlockables system**. For setting a child's starting avatar and general child setup, see [Children](Children.md).

---

## How Unlocking Works

Parents define a **catalogue** of avatars. Each entry has an unlock requirement, and a child unlocks it automatically once they meet that requirement. Unlock state is derived live from the child's stats — there's nothing to award manually.

| Unlock type | Unlocks when… | Measured against |
|-------------|----------------|------------------|
| `free` | Always available | — |
| `level` | The child reaches the given [level](Levels-and-XP.md) | Current level |
| `points` | The child's lifetime earned points reach the value | `total_points_earned` |
| `streak` | The child's best streak reaches the value (days) | `best_streak` |

---

## The Default Catalogue

TaskMate ships with a starter catalogue so the feature is useful out of the box. Parents can replace the whole list.

| Avatar | Icon | Unlocks |
|--------|------|---------|
| Starter | `mdi:account-circle` | Always available (free) |
| Rocket | `mdi:rocket-launch` | Level 3 |
| Robot | `mdi:robot-happy` | Level 5 |
| Ninja | `mdi:ninja` | Level 10 |
| Royalty | `mdi:crown` | 500 points earned |
| Champion | `mdi:trophy` | 1000 points earned |
| On Fire | `mdi:fire` | 7-day streak |
| Diamond | `mdi:diamond-stone` | 30-day streak |

---

## Managing the Catalogue

Open the avatar catalogue from the **Admin Panel** (the "Manage avatars" action). Each row needs an MDI icon and an unlock requirement (type plus value). You can add and delete rows and then save to replace the whole catalogue.

Each catalogue entry stores:

| Field | Description |
|-------|-------------|
| `id` | Stable identifier (defaults to the icon if omitted) |
| `label` | Display name, e.g. "Rocket" |
| `icon` | MDI icon (required) |
| `unlock_type` | `free`, `level`, `points`, or `streak` |
| `unlock_value` | The threshold (ignored for `free`) |

Rows without an icon are dropped on save.

---

## Choosing an Avatar

### Children (self-service)

On the [child card](Dashboard-Cards.md) and the [kiosk](Kiosk-Mode.md), tapping the avatar opens a picker showing the catalogue. Unlocked avatars are selectable; locked ones are dimmed and show their requirement. The picker is available when:

- The card's `allow_avatar_change` option is not set to `false` (it's on by default), and
- The child has more than one unlocked avatar to choose from

A child can only switch to an avatar they've **unlocked**.

### `choose_avatar` service

The picker calls this service under the hood; you can also call it directly:

```yaml
service: taskmate.choose_avatar
data:
  child_id: a8c8376a
  icon: mdi:rocket-launch
```

| Field | Required | Description |
|-------|----------|-------------|
| `child_id` | Yes | The child switching avatar |
| `icon` | Yes | The MDI icon of an **unlocked** catalogue avatar |

The service enforces the unlock check — choosing a locked avatar fails. Parents can set any catalogue avatar (including locked ones) via the child's settings in the Admin Panel, which bypasses the unlock requirement.

---

## Sensor Attributes

Each child's entry in the `sensor.taskmate_overview` `children` attribute carries:

- `avatar` — the child's currently selected avatar icon
- `avatar_options` — the catalogue annotated with per-child unlock state

Each `avatar_options` item contains:

| Field | Description |
|-------|-------------|
| `id` | The avatar's ID |
| `label` | Display name |
| `icon` | MDI icon |
| `unlocked` | `true` if this child has met the requirement |
| `requirement` | Human-readable requirement, e.g. `Level 3`, `500 earned`, `7-day streak` (empty for free) |

---

## Related

- [Children](Children.md) — child setup and the starting avatar
- [Levels and XP](Levels-and-XP.md) — the level thresholds that gate avatars
- [Bonus Points](Bonus-Points.md) — streaks and earned-point totals that unlock avatars
- [Dashboard Cards](Dashboard-Cards.md) — the child card avatar picker
- [Services](Services.md) — the `choose_avatar` service
