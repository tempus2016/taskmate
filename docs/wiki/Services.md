# Services

TaskMate provides a comprehensive set of services that can be called from Home Assistant automations, scripts, and other integrations. All services are under the `taskmate` domain.

## Chore Management

### taskmate.complete_chore
Mark a chore as completed by a child.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chore_id` | String | Yes | The ID of the chore to complete |
| `child_id` | String | Yes | The ID of the child completing the chore |

**Example:**
```yaml
service: taskmate.complete_chore
data:
  chore_id: "chore_123"
  child_id: "child_456"
```

**Notes:** Points are held until approved if approval is required. The chore will enter a pending state awaiting parent review.

---

### taskmate.approve_chore
Approve a completed chore and award points to the child.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `completion_id` | String | Yes | The ID of the chore completion to approve |

**Example:**
```yaml
service: taskmate.approve_chore
data:
  completion_id: "completion_789"
```

---

### taskmate.reject_chore
Reject a completed chore without awarding points.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `completion_id` | String | Yes | The ID of the chore completion to reject |

**Example:**
```yaml
service: taskmate.reject_chore
data:
  completion_id: "completion_789"
```

---

## Reward System

### taskmate.claim_reward
Allow a child to claim a reward using their points.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `reward_id` | String | Yes | The ID of the reward to claim |
| `child_id` | String | Yes | The ID of the child claiming the reward |

**Example:**
```yaml
service: taskmate.claim_reward
data:
  reward_id: "reward_123"
  child_id: "child_456"
```

**Notes:** Points are not deducted until the claim is approved by a parent.

---

### taskmate.approve_reward
Approve a pending reward claim and deduct points from the child.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claim_id` | String | Yes | The ID of the reward claim to approve |

**Example:**
```yaml
service: taskmate.approve_reward
data:
  claim_id: "claim_789"
```

---

### taskmate.reject_reward
Reject a pending reward claim without deducting points.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `claim_id` | String | Yes | The ID of the reward claim to reject |

**Example:**
```yaml
service: taskmate.reject_reward
data:
  claim_id: "claim_789"
```

---

## Point Adjustments

### taskmate.add_points
Award bonus points to a child.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `child_id` | String | Yes | The ID of the child to add points to |
| `points` | Number | Yes | The number of points to add (1-10000) |
| `reason` | String | No | Optional reason for the bonus |

**Example:**
```yaml
service: taskmate.add_points
data:
  child_id: "child_456"
  points: 25
  reason: "Helped with yard work"
```

---

### taskmate.remove_points
Remove points from a child (penalty).

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `child_id` | String | Yes | The ID of the child to remove points from |
| `points` | Number | Yes | The number of points to remove (1-10000) |
| `reason` | String | No | Optional reason for the penalty |

**Example:**
```yaml
service: taskmate.remove_points
data:
  child_id: "child_456"
  points: 10
  reason: "Did not complete chore on time"
```

---

## Chore Display Configuration

### taskmate.set_chore_order
Set the display order of chores for a specific child.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `child_id` | String | Yes | The ID of the child to set chore order for |
| `chore_order` | Object | Yes | Ordered list of chore IDs |

**Example:**
```yaml
service: taskmate.set_chore_order
data:
  child_id: "child_456"
  chore_order:
    - "chore_001"
    - "chore_002"
    - "chore_003"
```

---

## Audio Preview

### taskmate.preview_sound
Preview a completion sound effect in the browser (useful for testing sounds).

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sound` | Select | Yes | The sound effect to preview |

**Available Sounds:**
- `none` - No sound
- `coin` - Coin collection sound
- `levelup` - Level up sound
- `fanfare` - Fanfare trumpet sound
- `chime` - Bell chime sound
- `powerup` - Power-up sound
- `undo` - Undo/retract sound
- `fart1` through `fart10` - Various fart sound effects
- `fart_random` - Random fart sound

**Example:**
```yaml
service: taskmate.preview_sound
data:
  sound: "coin"
```

---

## Penalty Management

### taskmate.add_penalty
Create a new penalty definition.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | Yes | The name of the penalty |
| `points` | Number | Yes | Points deducted when applied (1-10000) |
| `description` | String | No | Optional description of the penalty |
| `icon` | String | No | MDI icon for the penalty |
| `assigned_to` | Object | No | List of child IDs this penalty applies to (empty for all) |

**Example:**
```yaml
service: taskmate.add_penalty
data:
  name: "Backtalk"
  points: 5
  description: "Talking back to parent"
  icon: "mdi:close-circle"
  assigned_to:
    - "child_001"
    - "child_002"
```

---

### taskmate.update_penalty
Update an existing penalty definition.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `penalty_id` | String | Yes | The ID of the penalty to update |
| `name` | String | No | New name for the penalty |
| `points` | Number | No | New points value |
| `description` | String | No | New description |
| `icon` | String | No | New icon |
| `assigned_to` | Object | No | New list of assigned child IDs |

**Example:**
```yaml
service: taskmate.update_penalty
data:
  penalty_id: "penalty_123"
  points: 10
  description: "Updated description for backtalk penalty"
```

---

### taskmate.remove_penalty
Remove a penalty definition.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `penalty_id` | String | Yes | The ID of the penalty to remove |

**Example:**
```yaml
service: taskmate.remove_penalty
data:
  penalty_id: "penalty_123"
```

---

### taskmate.apply_penalty
Apply a penalty to a child, deducting points.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `penalty_id` | String | Yes | The ID of the penalty to apply |
| `child_id` | String | Yes | The ID of the child to apply the penalty to |

**Example:**
```yaml
service: taskmate.apply_penalty
data:
  penalty_id: "penalty_123"
  child_id: "child_456"
```

---

## Bonus Management

### taskmate.add_bonus
Create a new bonus definition.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | String | Yes | The name of the bonus |
| `points` | Number | Yes | Points awarded when applied (1-10000) |
| `description` | String | No | Optional description of the bonus |
| `icon` | String | No | MDI icon for the bonus |
| `assigned_to` | Object | No | List of child IDs this bonus applies to (empty for all) |

**Example:**
```yaml
service: taskmate.add_bonus
data:
  name: "Perfect Week"
  points: 25
  description: "Completed all chores for the week"
  icon: "mdi:star"
  assigned_to:
    - "child_001"
    - "child_002"
```

---

### taskmate.update_bonus
Update an existing bonus definition.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bonus_id` | String | Yes | The ID of the bonus to update |
| `name` | String | No | New name for the bonus |
| `points` | Number | No | New points value |
| `description` | String | No | New description |
| `icon` | String | No | New icon |
| `assigned_to` | Object | No | New list of assigned child IDs |

**Example:**
```yaml
service: taskmate.update_bonus
data:
  bonus_id: "bonus_123"
  points: 50
  description: "Updated to higher reward"
```

---

### taskmate.remove_bonus
Remove a bonus definition.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bonus_id` | String | Yes | The ID of the bonus to remove |

**Example:**
```yaml
service: taskmate.remove_bonus
data:
  bonus_id: "bonus_123"
```

---

### taskmate.apply_bonus
Apply a bonus to a child, awarding points.

**Parameters:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `bonus_id` | String | Yes | The ID of the bonus to apply |
| `child_id` | String | Yes | The ID of the child to apply the bonus to |

**Example:**
```yaml
service: taskmate.apply_bonus
data:
  bonus_id: "bonus_123"
  child_id: "child_456"
```

---

## Dynamic Chore Creation

### taskmate.add_chore
Create a new chore dynamically from an automation or script. This is useful for creating just-in-time chores in response to Home Assistant events.

**Parameters:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | String | Yes | - | The name of the chore |
| `description` | String | No | - | Optional description of the chore |
| `points` | Number | No | 10 | Points awarded when completed (1-10000) |
| `assigned_to` | Object | No | - | List of child IDs to assign to (empty assigns to all) |
| `time_category` | Select | No | anytime | When the chore should be completed: `morning`, `afternoon`, `evening`, `night`, `anytime` |
| `one_shot` | Boolean | No | false | If true, this is a one-time chore that expires after completion or at end of day |
| `requires_approval` | Boolean | No | true | If true, a parent must approve completion before points are awarded |

**Example - Simple Chore:**
```yaml
service: taskmate.add_chore
data:
  name: "Water the plants"
  points: 15
```

**Example - One-Shot Chore:**
```yaml
service: taskmate.add_chore
data:
  name: "Pick up package at front door"
  description: "Amazon delivery has arrived"
  points: 20
  one_shot: true
  requires_approval: false
  assigned_to:
    - "child_001"
```

**Example - Time-Specific Chore:**
```yaml
service: taskmate.add_chore
data:
  name: "Pack lunch for school"
  time_category: "morning"
  points: 10
  requires_approval: false
```

**Use Cases:**
- Create a chore when a door sensor opens (packages have arrived)
- Dynamic chores based on weather (water lawn only when temperature is moderate)
- Time-limited chores for appointments or events
- Chores triggered by presence changes (someone left home)
- One-time urgent tasks as they arise

---

## Accessing Services

### Home Assistant Developer Tools

1. Go to **Developer Tools** > **Services** in Home Assistant
2. Search for a service starting with `taskmate.`
3. Fill in the parameters using the form or YAML editor
4. Click **Call Service**

### Automations and Scripts

Include service calls in your automations or scripts:

```yaml
automation:
  - alias: "Award bonus for early completion"
    trigger:
      platform: template
      value_template: "{{ states('sensor.chore_completion_time') | int < 300 }}"
    action:
      service: taskmate.apply_bonus
      data:
        bonus_id: "bonus_speed"
        child_id: "{{ states('input_select.current_child') }}"
```

### Button Entities

Create automation-triggering buttons in Home Assistant for quick service calls:

```yaml
button:
  - platform: template
    buttons:
      award_perfect_week:
        friendly_name: "Award Perfect Week Bonus"
        press:
          service: taskmate.apply_bonus
          data:
            bonus_id: "bonus_perfect_week"
            child_id: "{{ states('input_select.selected_child') }}"
```
