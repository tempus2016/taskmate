# Visibility Operators Reference

## Quick Reference

| Operator | Symbol | Use Case | Example |
|----------|--------|----------|---------|
| **Equals** | `=` | Exact text match | Entity: `binary_sensor.door`, State: `open` |
| **Not Equal** | `≠` | Inverted match | Entity: `input_boolean.guest_mode`, State: `on` |
| **Greater or Equal** | `≥` | Numeric threshold (at or above) | Entity: `sensor.battery`, State: `80` |
| **Less or Equal** | `≤` | Numeric threshold (at or below) | Entity: `sensor.moisture`, State: `30` |
| **Greater Than** | `>` | Numeric threshold (above) | Entity: `sensor.temp`, State: `25` |
| **Less Than** | `<` | Numeric threshold (below) | Entity: `sensor.temp`, State: `0` |

---

## Detailed Operator Guide

### Equals (`=`)

**Description:** Show the chore when the entity state exactly matches the target value (case-insensitive).

**Best For:**
- Binary states: `on`, `off`
- Location states: `home`, `away`, `work`
- Custom string values: `running`, `idle`, `locked`
- Friendly name states

**Examples:**

```
Entity: binary_sensor.dishwasher
Operator: Equals
State: on
→ Shows when dishwasher IS running
```

```
Entity: person.john
Operator: Equals
State: home
→ Shows when John IS home
```

```
Entity: cover.garage_door
Operator: Equals
State: open
→ Shows when garage door IS open
```

**Technical Details:**
- Matching is case-insensitive (`On` matches `on`, `HOME` matches `home`)
- Whitespace is trimmed
- Works with any string state value

---

### Not Equal (`≠`)

**Description:** Show the chore when the entity state does NOT match the target value (inverse of Equals).

**Best For:**
- Hiding chores under certain conditions
- Conditional availability: "show unless..."
- Input booleans for feature gates

**Examples:**

```
Entity: input_boolean.guest_mode
Operator: Not Equal
State: on
→ Shows when guests are NOT visiting
```

```
Entity: person.parent
Operator: Not Equal
State: away
→ Shows when at least one parent is NOT away
```

```
Entity: binary_sensor.school_open
Operator: Not Equal
State: on
→ Shows when school is NOT in session
```

**Technical Details:**
- Inverted logic of Equals
- Also case-insensitive
- Useful for permission/restriction patterns

---

### Greater Than or Equal (`≥`)

**Description:** Show the chore when the entity state value is greater than or equal to the target number.

**Best For:**
- Minimum thresholds
- "At least" conditions
- Battery levels, stock quantities, percentages

**Examples:**

```
Entity: sensor.battery_percent
Operator: ≥
State: 80
→ Shows when battery is 80% or higher
```

```
Entity: sensor.outdoor_temp
Operator: ≥
State: 20
→ Shows when temperature is 20°C or warmer
```

```
Entity: sensor.available_disk_space
Operator: ≥
State: 5
→ Shows when at least 5GB free (if sensor provides GB values)
```

**Technical Details:**
- Both values are converted to numbers for comparison
- Decimal values supported: `22.5`, `10.25`
- If entity state can't be converted to a number, falls back to string matching

---

### Less Than or Equal (`≤`)

**Description:** Show the chore when the entity state value is less than or equal to the target number.

**Best For:**
- Maximum thresholds
- "No more than" conditions
- Moisture levels, humidity, cost limits

**Examples:**

```
Entity: sensor.soil_moisture_percent
Operator: ≤
State: 30
→ Shows when soil is 30% moist or drier
```

```
Entity: sensor.indoor_humidity
Operator: ≤
State: 60
→ Shows when humidity is 60% or lower
```

```
Entity: number.temperature_threshold
Operator: ≤
State: 15
→ Shows when threshold is set to 15°C or lower
```

**Technical Details:**
- Converts both values to numbers
- Decimal values supported
- Common for sensor-based automation

---

### Greater Than (`>`)

**Description:** Show the chore when the entity state value is strictly greater than (not equal to) the target number.

**Best For:**
- Exclusive minimum thresholds
- "More than" conditions
- Situations where the threshold value itself should hide the chore

**Examples:**

```
Entity: sensor.outdoor_temp
Operator: >
State: 20
→ Shows when temperature is ABOVE 20°C (20° itself doesn't show)
```

```
Entity: counter.days_since_cleaning
Operator: >
State: 7
→ Shows when MORE than 7 days have passed
```

```
Entity: sensor.room_occupancy_count
Operator: >
State: 0
→ Shows when room has more than 0 people (i.e., at least 1)
```

**Technical Details:**
- Stricter than `≥` (excludes the boundary value)
- Useful when the exact threshold value has special meaning
- Numeric conversion with decimal support

---

### Less Than (`<`)

**Description:** Show the chore when the entity state value is strictly less than (not equal to) the target number.

**Best For:**
- Exclusive maximum thresholds
- "Less than" conditions
- Situations where the threshold value itself should hide the chore

**Examples:**

```
Entity: sensor.outdoor_temp
Operator: <
State: 0
→ Shows when temperature is BELOW 0°C (freezing point)
```

```
Entity: sensor.snow_depth_cm
Operator: <
State: 5
→ Shows when snow is less than 5cm deep
```

```
Entity: sensor.water_level_percent
Operator: <
State: 25
→ Shows when water level is BELOW 25%
```

**Technical Details:**
- Stricter than `≤` (excludes the boundary value)
- Useful for critical thresholds
- Numeric conversion with decimal support

---

## Comparison Matrix

| Entity State | ≥ 50 | > 50 | ≤ 50 | < 50 | = 50 | ≠ 50 |
|--------------|------|------|------|------|------|------|
| 30 | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ |
| 50 | ✅ | ❌ | ✅ | ❌ | ✅ | ❌ |
| 70 | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |

---

## Real-World Examples

### Example 1: Dishwasher Chores

```
Chore: "Load Dishwasher"
Entity: binary_sensor.dishwasher
Operator: Equals
State: off
→ Shows when dishwasher is NOT running (i.e., ready to load)
```

**Why this works:** When the dishwasher is off, children can load it. When it's running, the chore isn't helpful.

---

### Example 2: Temperature-Based Outdoor Chores

```
Chore: "Rake Leaves"
Entity: sensor.outdoor_temperature
Operator: ≥
State: 15
→ Shows when temperature is 15°C or warmer
```

**Why this works:** You only want kids doing outdoor work in reasonable weather.

---

### Example 3: Watering Plants

```
Chore: "Water Plants"
Entity: sensor.soil_moisture
Operator: ≤
State: 40
→ Shows when soil moisture is 40% or lower
```

**Why this works:** No need to water if the soil is already moist.

---

### Example 4: Guest Mode

```
Chore: "Clean Room"
Entity: input_boolean.guests_arriving_today
Operator: Equals
State: on
→ Shows when guests are expected
```

**Why this works:** You want kids cleaning their rooms when guests are coming.

---

### Example 5: School Day Chores

```
Chore: "Lunch Prep"
Entity: input_boolean.school_day
Operator: Equals
State: on
→ Shows only on school days
```

**Why this works:** Lunch prep is only relevant on days when someone is going to school.

---

## Numeric Conversion Rules

When using comparison operators (`≥`, `≤`, `>`, `<`), TaskMate converts state values to numbers:

### Valid Conversions
- `"22"` → `22`
- `"22.5"` → `22.5`
- `"100%"` → Fails (% breaks conversion, falls back to string)
- `"-5"` → `-5` (negative numbers work)

### Invalid Conversions (Falls Back to String Matching)
- `"on"`, `"off"` → Can't convert to number
- `"running"`, `"idle"` → Can't convert to number
- `"22.5.1"` → Multiple decimals, can't convert

**When conversion fails:**
- Operator comparison is skipped
- Falls back to checking if state equals the target string (case-insensitive)
- Useful safety net for mixed string/number states

---

## Tips & Tricks

### Tip 1: Combine with Input Booleans

Create custom `input_boolean` helpers for complex logic:

```yaml
# In configuration.yaml
input_boolean:
  chore_day_weekend:
    name: Chore Day - Weekend
  chore_day_schoolday:
    name: Chore Day - School Day
```

Then use them for visibility:
```
Chore: "Yard Work"
Entity: input_boolean.chore_day_weekend
Operator: Equals
State: on
```

### Tip 2: Use Template Sensors

Create template sensors that calculate conditions:

```yaml
template:
  - sensor:
      - name: "Is Cold"
        unique_id: sensor_is_cold
        state: "{{ states('sensor.temperature') | float(0) < 10 }}"
```

Then use in visibility:
```
Entity: sensor.is_cold
Operator: Equals
State: "true"
```

### Tip 3: Test in Developer Tools

Before setting up visibility, verify your entity state:

1. Go to **Developer Tools > States**
2. Search for your entity
3. Check the exact state value
4. Use that value in Visibility State field

### Tip 4: Chain Multiple Conditions

While single conditions are supported, you can simulate AND/OR by:
- Creating helper automations that update input_booleans
- Using template sensors to combine multiple entity states
- Setting up multiple chores with complementary visibility rules

---

## Troubleshooting

### "Entity not found"
- Check the entity ID spelling in Developer Tools > States
- Ensure the integration providing the entity is installed and running
- Wait for Home Assistant to fully load all integrations

### "Numeric comparison not working"
- Verify the entity state is actually numeric (no units or symbols)
- Check Developer Tools > States for the exact value
- Try converting to string comparison if state has units

### "Chore shows even when condition isn't met"
- Double-check the Visibility State value matches exactly
- For numeric operators, ensure the number is valid
- Wait 30 seconds for the visibility update cycle
- Reload the TaskMate integration

---

## See Also

- [[Dynamic Chore Visibility]] — Feature overview and setup
- [[Configuration Guide]] — Complete TaskMate setup
