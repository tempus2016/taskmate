# Dynamic Chore Visibility

## Overview

Dynamic Chore Visibility allows you to conditionally show or hide chores on the child card based on the state of any Home Assistant entity. This powerful feature enables you to create context-aware chore lists that automatically appear or disappear based on real-world conditions.

**Example Use Cases:**
- Show dishwasher-loading chores only when the dishwasher is running
- Show watering chores only when soil moisture drops below a threshold
- Show yard work only when it's warm enough outside
- Hide chores when guests are visiting using an input_boolean

## How It Works

When you create or edit a chore, you can set three optional fields:

1. **Visibility Entity** — A Home Assistant entity ID that controls the chore's visibility
2. **Visibility Operator** — How to compare the entity's state with your target value
3. **Visibility State** — The target value to compare against

The chore appears on the child card **only when** the visibility condition is met.

### Example Configuration

| Field | Value | Meaning |
|-------|-------|---------|
| Visibility Entity | `binary_sensor.dishwasher` | Watch the dishwasher entity |
| Visibility Operator | `Equals` | When it matches exactly |
| Visibility State | `on` | The "on" state |

**Result:** The chore only appears when the dishwasher is running.

## Supported Entity Types

Visibility works with any Home Assistant entity:
- **Binary Sensors** — `binary_sensor.dishwasher`, `binary_sensor.door_open`
- **Sensors** — `sensor.temperature`, `sensor.soil_moisture`, `sensor.battery_percent`
- **Input Booleans** — `input_boolean.guest_mode`, `input_boolean.school_day`
- **Switches** — `switch.laundry_room`, `switch.office_light`
- **Numbers** — `number.temperature_threshold`
- **Any other entity with a state**

## Common Use Cases

### Equipment-Based Chores

**Show chores only when equipment is in use:**

```
Entity: binary_sensor.dishwasher
Operator: Equals
State: on
→ Shows "Load dishwasher" only when dishwasher is running
```

```
Entity: binary_sensor.dryer
Operator: Equals
State: on
→ Shows "Fold laundry" only when dryer is running
```

### Sensor-Based Chores

**Show chores based on numeric thresholds:**

```
Entity: sensor.soil_moisture
Operator: ≤ (Less than or equal)
State: 30
→ Shows "Water plants" when moisture ≤ 30%
```

```
Entity: sensor.temperature
Operator: ≥ (Greater than or equal)
State: 20
→ Shows "Yard work" when temperature ≥ 20°C
```

### Conditional Availability

**Show/hide based on family status:**

```
Entity: input_boolean.guest_mode
Operator: Not Equal
State: on
→ Shows chores only when guests are NOT visiting
```

```
Entity: input_boolean.school_day
Operator: Equals
State: on
→ Shows "Lunch prep" only on school days
```

### Time-Based Conditions

**Use time-of-day helpers for scheduling:**

```
Entity: binary_sensor.is_daytime
Operator: Equals
State: on
→ Shows outdoor chores only during daylight
```

## Technical Details

### Numeric Comparison

When using comparison operators (≥, ≤, >, <), the entity state is automatically converted to a number:

- Valid: `sensor.temperature` with state `22.5` using operator `>`
- Valid: `sensor.battery_percent` with state `75` using operator `≥`
- Fallback: If conversion fails, string matching is used instead

### String Matching

For `Equals` and `Not Equal` operators:

- Case-insensitive matching
- Exact value required
- Works with any state value: `on`, `off`, `home`, `away`, `running`, custom values, etc.

### Entity Unavailability

If an entity becomes unavailable or its state can't be read:

- The chore **defaults to visible** for safety
- Parent services like `taskmate.complete_chore` still work on hidden chores
- Check Home Assistant's Developer Tools > States to verify entity availability

### Update Frequency

Visibility checks happen every **30 seconds** (coordinator refresh interval). This means:
- Changes to entity state take up to 30 seconds to affect chore visibility
- This is a balancing act between responsiveness and performance
- Consider this when setting up rapid state changes

## Setting Up Visibility

1. Go to **Settings → Integrations → TaskMate → Configure**
2. Select **Manage Chores**
3. Create a new chore or edit an existing one
4. In **Step 1**, set the optional visibility fields:
   - **Show when entity is** — Enter your entity ID
   - **How to compare** — Select the operator
   - **Value to compare** — Enter the target value
5. Complete **Step 2** (schedule selection)
6. Save the chore

The chore will now appear/disappear based on the visibility condition.

## Clearing Visibility

To disable visibility filtering on a chore:

1. Edit the chore
2. Leave the **Show when entity is** field **blank**
3. Save

The chore will always be visible on the child card.

## Limitations & Notes

- **Single condition per chore** — Currently supports one visibility condition (AND/OR logic coming in future versions)
- **30-second refresh** — Visibility updates every 30 seconds, not in real-time
- **Card display only** — Visibility only hides chores from the child card. Parent API calls and services can still complete hidden chores
- **Numeric conversion** — Non-numeric values fall back to string matching automatically

## Troubleshooting

### Chore isn't appearing when I expect it to

1. **Check the entity exists** — Go to Developer Tools > States and search for your entity
2. **Verify the state** — What's the current state value?
3. **Test the operator** — Is the state actually matching your condition?
4. **Wait 30 seconds** — Visibility updates every 30 seconds
5. **Check entity type** — For numeric operators, ensure the entity can be converted to a number

### Entity state shows "unavailable" or "unknown"

This means the entity isn't providing data to Home Assistant:
- Check the integration that provides this entity
- Restart Home Assistant
- The chore will default to visible in the meantime

### Chore shows for both matching and non-matching states

This usually means:
- The `Visibility Entity` field is empty (clear it completely if you want to disable visibility)
- The entity state doesn't match your `Visibility State` exactly
- For numeric operators, the state might not be a valid number

## Future Enhancements

Planned improvements to visibility:
- **Multiple conditions** — Combine visibility rules with AND/OR logic
- **Instant updates** — Real-time visibility changes instead of 30-second interval
- **Templates** — Pre-built visibility configurations for common scenarios
- **Negation** — Hide when condition is met (inverse logic)

## Questions or Issues?

If you encounter problems with visibility:

1. Check Home Assistant's logs for errors
2. Verify your entity ID in Developer Tools > States
3. Test manually in Developer Tools > Call Service
4. Report issues on [GitHub Issues](https://github.com/tempus2016/taskmate/issues)
