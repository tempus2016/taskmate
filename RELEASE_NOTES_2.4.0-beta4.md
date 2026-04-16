# TaskMate 2.4.0-beta4 Release Notes

**Release Date:** April 2025  
**Status:** Beta Release

---

## Overview

TaskMate 2.4.0-beta4 introduces **dynamic chore visibility** — a powerful new feature that allows chores to automatically appear or disappear based on Home Assistant entity states. This enables automation-triggered chores that respond to your smart home in real-time.

---

## 🎉 New Features

### Dynamic Chore Visibility

Chores can now be conditionally visible based on Home Assistant entity states. This allows you to:

- **Show chores when conditions are met** — e.g., show "water plants" only when the soil moisture is below 30%
- **Hide chores when conditions change** — e.g., hide "lock doors" when someone is away
- **Automate chore assignments** — trigger chores based on device states, sensor readings, or boolean helpers

#### Supported Entities

The visibility feature works with these Home Assistant domain types:

- `binary_sensor` — detect on/off states (motion sensors, presence, etc.)
- `input_boolean` — manual toggles controlled by automations
- `switch` — smart switch states
- `sensor` — numeric sensors (temperature, humidity, power, etc.)
- `number` — numeric helpers and input numbers

#### How It Works

1. When creating or editing a chore, set:
   - **Visibility Entity** — which Home Assistant entity to monitor
   - **Visibility State** — what state or value to match
   - **Comparison Operator** — how to compare values

2. The chore will only appear on the child card when the entity state matches your criteria

3. Updates are evaluated every 30 seconds via the coordinator refresh cycle

#### Example Use Cases

| Scenario | Entity | Operator | State | Result |
|----------|--------|----------|-------|--------|
| Show "water plants" when soil dry | `sensor.soil_moisture` | Less than | 30 | Chore appears when moisture ≤ 30% |
| Show "car wash" when car is home | `binary_sensor.car_home` | Equals | on | Chore appears only when car is detected |
| Hide chores while away | `input_boolean.family_away` | Equals | off | Chore hidden when away mode is on |
| Show "pool duty" when temperature hot | `sensor.outdoor_temp` | Greater than | 25 | Chore appears when temp > 25°C |

#### Operators Available

- **Equals (exact match)** — string or case-insensitive matching
- **Greater than or equal (≥)** — numeric comparison
- **Less than or equal (≤)** — numeric comparison
- **Greater than (>)** — numeric comparison
- **Less than (<)** — numeric comparison
- **Not equal (≠)** — numeric or string comparison

---

## 🔧 Improvements

### Configurable State Matching

The visibility feature supports flexible state matching:

- **String matching** — exact state values like `on`, `off`, `home`, etc. (case-insensitive)
- **Numeric comparisons** — threshold-based matching for sensors (e.g., temperature > 25, power >= 100W)
- **Entity attributes** — checks state first, then falls back to entity attributes if no direct match

### Enhanced Config Flow UI

- **User-friendly dropdowns** for comparison operators (no syntax required)
- **Entity selector** with domain filtering for easier entity selection
- **Clear descriptions** of what each setting does
- **Translations** in multiple languages (including French)

### Safe Defaults

- Chores **default to visible** if the visibility entity doesn't exist or becomes unavailable
- This ensures chores don't disappear unexpectedly due to connectivity issues
- Useful for testing with automations or sensors that may not exist yet

---

## 🐛 Bug Fixes

- Fixed review issues with visibility_entity field handling
- Improved state parsing for edge cases in entity attributes
- Corrected fallback behavior for missing or unavailable entities

---

## 📋 Testing

This beta release includes comprehensive test coverage:

- **7 visibility tests** covering state matching, numeric comparisons, and edge cases
- **56 total tests** ensuring all coordinator logic works correctly
- All tests passing with numeric operators (>=, <=, >, <, !=)

---

## 🌍 Languages

- **English** — Full support
- **French** — Complete translation (thanks to @cabatech)
- Additional languages welcome via contributions

---

## 📝 Configuration Example

### JSON Format

```json
{
  "name": "Water Plants",
  "points": 10,
  "visibility_entity": "sensor.soil_moisture",
  "visibility_state": "30",
  "visibility_operator": "lte",
  "assigned_to": ["child_id"],
  "requires_approval": false
}
```

### Configuration Flow

When adding or editing a chore:

1. Set the chore details (name, points, etc.)
2. Go to **Visibility Settings**
3. Select the entity to monitor
4. Choose the comparison operator
5. Enter the threshold or target state
6. Save

---

## ⚠️ Known Limitations

- Visibility checks update every 30 seconds (coordinator refresh interval)
- Entity state changes may not be reflected instantly on the child card
- Numeric comparisons require valid float conversion; invalid values fall back to string matching
- Visibility only affects card display; it doesn't prevent manual API completion

---

## 🚀 Upgrade Notes

**No breaking changes** — this release is fully backward compatible:

- Existing chores without visibility settings work unchanged
- The visibility feature is optional and disabled by default
- All previous chore configurations remain valid

---

## 📦 What's Included

- Core integration with dynamic visibility logic
- Config flow UI for setting up visibility rules
- 14 Lovelace cards (unchanged from previous releases)
- Full translation support
- Comprehensive test suite

---

## 🔍 Technical Details

### Implementation

- **Coordinator:** `_is_visibility_entity_active()` method handles all visibility logic
- **Models:** Extended `Chore` dataclass with visibility fields
- **Config Flow:** Three entry points (add, edit, bulk add) support visibility settings
- **Frontend:** Child card filters chores based on visibility state
- **Storage:** Visibility settings persisted with chore data

### Performance

- No performance impact when visibility feature is disabled
- Minimal overhead for enabled chores (one state lookup per 30-second refresh)
- All checks use efficient state lookups from Home Assistant

---

## 💬 Feedback & Reporting Issues

Found a bug or have a feature request? Open an issue on GitHub:  
👉 https://github.com/tempus2016/taskmate/issues

---

## 📄 License

TaskMate is licensed under the MIT License.

---

**Thank you for testing TaskMate 2.4.0-beta4!**

Your feedback helps us make TaskMate better. Please report any issues or suggestions.
