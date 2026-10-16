# Timed Tasks

Timed Tasks let children earn points based on how long they spend on an activity rather than a simple tick-off. Ideal for reading, practising an instrument, or any chore where effort = duration.

![The Child card](images/card-child.png)

---

## How It Works

```
Child starts timer → Timer runs → Child stops timer → Points calculated → Parent approves (optional)
```

Points are awarded based on a **rate**: X points per Y minutes. A 30-minute reading session at 10 points per 5 minutes earns 60 points.

---

## Configuring a Timed Task

When creating or editing a chore, set the **Task Type** to `timed`. Three additional fields appear:

| Field | Default | Description |
|-------|---------|-------------|
| **Timed Rate Points** | `10` | Points awarded per rate window |
| **Timed Rate Minutes** | `5` | Size of the rate window in minutes |
| **Daily Cap (minutes)** | `0` | Maximum minutes per day. `0` = unlimited. |

**Example:** Rate = 10 points per 5 minutes. A child who reads for 23 minutes earns `(23 ÷ 5) × 10 = 40 points` (partial windows are dropped, not rounded up).

**Formula:** `floor(total_seconds / (rate_minutes × 60)) × rate_points`

---

## The Timer Workflow

### Starting

1. Child taps **Start** on the timed chore in the child card
2. A live timer appears showing elapsed time
3. The session state is `running`

### Pausing

1. Child taps **Pause** — the timer freezes
2. The session state becomes `paused`
3. Child can resume later by tapping **Start** again
4. Multiple start/pause cycles are tracked as separate segments

### Stopping

1. Child taps **Stop** — the session ends
2. Total elapsed time is calculated from all segments
3. If the chore requires approval, a completion is created as pending
4. If no approval required, points are awarded immediately

### Daily Cap

When `timed_max_daily_minutes` is set (non-zero):

- The timer cannot be started once the cap is reached
- If the session would exceed the cap, the duration is clamped to the remaining allowance
- The daily cap resets at midnight

---

## Session Model

Each active timer is tracked as a `TimedSession`:

| Field | Description |
|-------|-------------|
| `state` | `running`, `paused`, or `stopped` |
| `segments` | List of `{start, end}` time windows |
| `total_seconds_today` | Cumulative elapsed seconds for the day |
| `session_date` | ISO date the session belongs to |

Sessions from previous days are automatically stopped and submitted at midnight.

---

## Services

### `taskmate.start_timed_task`

Start or resume a timed task timer.

| Field | Required | Description |
|-------|----------|-------------|
| `chore_id` | Yes | ID of the timed chore |
| `child_id` | Yes | ID of the child |

```yaml
service: taskmate.start_timed_task
data:
  chore_id: b3f9a12c
  child_id: a8c8376a
```

### `taskmate.pause_timed_task`

Pause a running timer. The child can resume later.

| Field | Required | Description |
|-------|----------|-------------|
| `chore_id` | Yes | ID of the timed chore |
| `child_id` | Yes | ID of the child |

```yaml
service: taskmate.pause_timed_task
data:
  chore_id: b3f9a12c
  child_id: a8c8376a
```

### `taskmate.stop_timed_task`

Stop the timer and submit for approval. Points are calculated from total elapsed time.

| Field | Required | Description |
|-------|----------|-------------|
| `chore_id` | Yes | ID of the timed chore |
| `child_id` | Yes | ID of the child |

```yaml
service: taskmate.stop_timed_task
data:
  chore_id: b3f9a12c
  child_id: a8c8376a
```

---

## Child Card Display

The child card shows timed tasks differently from standard chores:

- **Not started:** Shows Start button with the rate info (e.g. "10 pts / 5 min")
- **Running:** Shows a live elapsed timer, Pause button, and Stop button
- **Paused:** Shows frozen elapsed time, Start (resume) button, and Stop button
- **Stopped/completed:** Shows the earned points and duration

---

## Sensor Attributes

Active timed sessions appear in the activity sensor:

| Attribute | Description |
|-----------|-------------|
| `active_timed_sessions` | List of running/paused sessions with `chore_id`, `child_id`, `state`, `total_seconds_today`, `current_segment_start` |

Completion records for timed tasks include:

| Field | Description |
|-------|-------------|
| `timed_duration_seconds` | Total elapsed seconds for the session |

---

## Midnight Behaviour

- Stale sessions from previous days are automatically stopped and submitted
- A completion record is created with the elapsed time up to midnight
- The daily cap resets for the new day

---

## Tips

- **Set reasonable caps** for young children — 30 or 60 minutes prevents gaming the system
- **Use generous rate windows** (e.g. 10 pts per 15 min) for activities where sustained effort matters more than speed
- **Combine with approval** so parents can verify the child was actually doing the activity, not just running the timer

---

## Related

- [Chores](Chores.md) — chore configuration including task_type
- [Services](Services.md) — full service reference
- [Dashboard Cards](Dashboard-Cards.md) — child card timer display
