# TaskMate 2.5.0 Release Notes

**Release Date:** April 2025  
**Status:** Production Release

---

## Overview

TaskMate 2.5.0 marks the **official release of the dynamic chore visibility feature** with comprehensive multilingual support. All visibility functionality is fully tested, documented, and translated into 7 languages. This release includes significant improvements to user-facing documentation and help text throughout the configuration interface.

---

## ✨ New Features

### Comprehensive Visibility Feature Documentation
- **Enhanced field descriptions** in config flow with detailed examples for each use case
- **Operator explanations** in the visibility_operator selector with clear descriptions of each comparison type
- **Multilingual support** with consistent translations across 7 languages:
  - English (US & British variants)
  - French
  - Portuguese (Portugal & Brazil)
  - Norwegian (Bokmål & Nynorsk)

### Improved User Guidance
- **Detailed visibility_entity field help** with common entity ID examples (binary_sensor, sensor, input_boolean, switch)
- **Visibility_operator descriptions** explaining when to use each operator and what results to expect
- **Visibility_state context-aware guidance** showing different requirements for text vs. numeric operators
- **Practical examples** demonstrating real-world visibility configurations (e.g., showing dishwasher tasks when entity "on", showing soil moisture tasks when sensor ≤ 30%)

---

## 🐛 Bug Fixes (from beta7)

### Fixed: Visibility Fields Not Showing in State Attributes
- **Issue**: Visibility entity, operator, and state fields were saved to storage but not included in Home Assistant state attributes
- **Fix**: Added `visibility_entity`, `visibility_operator`, and `visibility_state` to the chore dictionary in sensor state attributes
- **Impact**: Visibility fields now properly display in Home Assistant's Developer Tools > States tab

### Fixed: Visibility Fields Lost After Step 2 in Edit Flow
- **Issue**: When editing a chore, visibility fields set in Step 1 were lost after submitting Step 2 (schedule selection)
- **Root Cause**: Edit chore Step 2 methods were incorrectly using `_chore_step1_data` (meant for add chore flow) instead of `_edited_chore` (for edit flow)
- **Fix**: Changed both `async_step_edit_chore_schedule_specific()` and `async_step_edit_chore_schedule_recurring()` to properly use `_edited_chore`
- **Impact**: Visibility configuration now persists correctly through the entire edit workflow

### Fixed: Missing Instance Variable Initialization
- **Issue**: The `_edited_chore` instance variable was not initialized in the `__init__` method
- **Fix**: Added proper initialization of `self._edited_chore = None` in TaskMateOptionsFlow constructor
- **Impact**: Improved reliability of multi-step config flows

### Fixed: Unable to Clear Visibility Entity
- **Issue**: Users couldn't remove visibility configuration once set
- **Root Cause**: `visibility_entity` field used EntitySelector which doesn't support empty values
- **Fix**: Changed `visibility_entity` field type from EntitySelector to plain str, allowing empty values
- **Impact**: Users can now disable visibility filtering by clearing the entity field

### Fixed: Not-Equals Operator Not Working for Strings
- **Issue**: When using the "!=" operator with string values, visibility logic failed
- **Root Cause**: Logic was checking for equality and falling through instead of properly inverting the check
- **Fix**: Explicitly handle not_equals with: `visibilityOK = !stateMatches` (inverse of equality)
- **Impact**: All 6 operators (equals, !=, >=, <=, >, <) now work correctly for both numeric and string matching

---

## ✅ Complete Feature List

### Dynamic Chore Visibility (Full Release)
- ✅ Visibility entity selection with domain filtering and clearing
- ✅ 6 comparison operators: equals, not_equals, >=, <=, >, <
- ✅ Numeric and string state matching with type-safe handling
- ✅ Safe fallback to visible if entity unavailable
- ✅ Frontend filtering in child card with real-time updates
- ✅ State attributes properly exposed in Home Assistant sensors
- ✅ Configuration persists across multi-step edit workflows
- ✅ Works with both specific_days and recurring schedules
- ✅ Comprehensive help text and examples in all languages
- ✅ 7 language translations with culturally appropriate guidance

### Core Features (Unchanged)
- ✅ Family chore management with points-based reward system
- ✅ Parent approval workflow for completed chores
- ✅ Flexible scheduling: specific days or recurring intervals
- ✅ Weekend points multiplier
- ✅ Streak tracking with customizable milestones and reset modes
- ✅ Perfect week bonus tracking
- ✅ Drag-and-drop chore reordering on child card
- ✅ Completion sound effects with preview
- ✅ Multi-language support (English, French, Norwegian variants, Portuguese variants)
- ✅ 14 Lovelace cards for different display needs
- ✅ Comprehensive penalty system
- ✅ Flexible history retention (30-365 days)

---

## 📋 Technical Details

### Files Modified
- `custom_components/taskmate/manifest.json`
  - Updated version to 2.5.0

- `custom_components/taskmate/strings.json`
  - Expanded visibility field descriptions with detailed operator explanations
  - Added `visibility_operator` selector section with descriptions for each option

- `custom_components/taskmate/translations/en.json`
  - Added visibility field translations
  - Added `visibility_operator` selector translations

- `custom_components/taskmate/translations/fr.json`
  - Added French visibility field translations
  - Added `visibility_operator` selector translations in French

- `custom_components/taskmate/translations/nb.json`
  - Added Norwegian Bokmål visibility field translations
  - Added `visibility_operator` selector translations in Norwegian

- `custom_components/taskmate/translations/nn.json`
  - Added Norwegian Nynorsk visibility field translations
  - Added `visibility_operator` selector translations in Nynorsk

- `custom_components/taskmate/translations/pt.json`
  - Added Portuguese visibility field translations
  - Added `visibility_operator` selector translations in Portuguese

- `custom_components/taskmate/translations/pt-BR.json`
  - Added Brazilian Portuguese visibility field translations
  - Added `visibility_operator` selector translations in Brazilian Portuguese

- `custom_components/taskmate/translations/en-GB.json`
  - Added British English visibility field translations
  - Added `visibility_operator` selector translations in British English

### Compatibility
- ✅ Fully backward compatible with existing chore configurations
- ✅ Chores without visibility settings work unchanged
- ✅ No breaking changes to API or data format
- ✅ All 7 translation files fully synchronized

---

## 🧪 Testing Checklist

### Visibility Feature Testing
- [ ] **Add new chore with visibility**
  - Add visibility entity, operator, and state in Step 1
  - Complete Step 2 (schedule selection)
  - Verify chore appears/disappears based on entity state
  - Check state attributes in Developer Tools > States

- [ ] **Edit existing chore with visibility**
  - Modify visibility settings in Step 1
  - Proceed to Step 2 (schedule selection)
  - Submit Step 2
  - Verify visibility fields persist and are applied correctly

- [ ] **Visibility field clearing**
  - Create a chore with visibility enabled
  - Edit the chore
  - Clear the visibility_entity field
  - Save and verify visibility is disabled

- [ ] **All operators**
  - Test equals with string values (e.g., entity state "on", "home")
  - Test not_equals with string values
  - Test >= operator with numeric sensor (e.g., 80)
  - Test <= operator with numeric sensor (e.g., 30)
  - Test > operator with numeric sensor
  - Test < operator with numeric sensor

- [ ] **Frontend filtering**
  - Set visibility condition that matches entity state
  - Verify chore appears on child card
  - Change entity state to not match condition
  - Verify chore disappears (within ~30 second refresh interval)
  - Change entity state back to match
  - Verify chore reappears

- [ ] **Multi-language support**
  - Change Home Assistant language to each supported language
  - Verify visibility field labels and descriptions display correctly
  - Verify operator selector translations are accurate

---

## 📝 Known Limitations

- Visibility checks update every 30 seconds (coordinator refresh interval)
- Numeric comparisons require valid float conversion; invalid values fall back to string matching
- Visibility only affects card display; it doesn't prevent API completion of hidden chores
- Single visibility condition per chore (AND/OR logic for multiple conditions not yet supported)

---

## 🚀 Future Considerations

- **Multiple visibility conditions** — Support AND/OR logic to combine multiple visibility rules
- **Instant visibility updates** — Explore reducing the 30-second refresh interval for faster feedback
- **Visibility templates** — Pre-built visibility configurations for common scenarios
- **Visibility history** — Track visibility state changes over time for analytics

---

## 📦 What's Included

- Full dynamic chore visibility feature with 6 comparison operators
- Comprehensive config flow help text in 7 languages
- State attributes exposure for developer integrations
- 14 Lovelace cards (unchanged from previous releases)
- Full translation support with synchronized translations
- Comprehensive test suite

---

## 💬 Feedback & Reporting Issues

Found a bug or have a feature request? Open an issue on GitHub:  
👉 https://github.com/tempus2016/taskmate/issues

Have suggestions for improving the visibility feature or translations? We'd love to hear from you!

---

## 📄 License

TaskMate is licensed under the MIT License.

---

**Thank you for upgrading to TaskMate 2.5.0!**

This release represents the completion and stabilization of the dynamic chore visibility feature with comprehensive user-facing documentation. Your feedback helps us continue to improve TaskMate. Please report any issues or suggestions you encounter.
