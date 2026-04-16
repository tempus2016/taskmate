# TaskMate 2.4.0-beta7 Release Notes

**Release Date:** April 2025  
**Status:** Beta Release

---

## Overview

TaskMate 2.4.0-beta7 focuses on **bug fixes and stability improvements** for the dynamic chore visibility feature introduced in beta4. All visibility fields are now properly persisted and displayed, and the multi-step chore editing flow correctly preserves configuration across steps.

---

## 🐛 Bug Fixes

### Fixed: Visibility Fields Not Showing in State Attributes
- **Issue**: Visibility entity, operator, and state fields were saved to storage but not included in Home Assistant state attributes
- **Fix**: Added `visibility_entity`, `visibility_operator`, and `visibility_state` to the chore dictionary in sensor state attributes
- **Impact**: Visibility fields now properly display in Home Assistant's Developer Tools > States tab

### Fixed: Visibility Fields Lost After Step 2 in Edit Flow
- **Issue**: When editing a chore, visibility fields set in Step 1 were lost after submitting Step 2 (schedule selection)
- **Root Cause**: Edit chore Step 2 methods were incorrectly using `_chore_step1_data` (meant for add chore flow) instead of `_edited_chore` (for edit flow), causing the chore to reload from storage without Step 1 modifications
- **Fix**: Changed both `async_step_edit_chore_schedule_specific()` and `async_step_edit_chore_schedule_recurring()` to properly use `_edited_chore` to preserve all Step 1 changes
- **Impact**: Visibility configuration now persists correctly through the entire edit workflow

### Fixed: Missing Instance Variable Initialization
- **Issue**: The `_edited_chore` instance variable was not initialized in the `__init__` method
- **Fix**: Added proper initialization of `self._edited_chore = None` in TaskMateOptionsFlow constructor
- **Impact**: Improved reliability of multi-step config flows

### Enhanced: Debug Logging for Visibility Fields
- **Added**: Detailed debug logging to track visibility field state through the edit chore workflow
- **Logged**: Entity, operator, and state values when saving specific_days and recurring chores
- **Benefit**: Easier troubleshooting of visibility configuration issues

---

## ✅ Verified Features

### Dynamic Chore Visibility (Complete)
- ✅ Visibility entity selection with domain filtering
- ✅ Comparison operators: equals, >=, <=, >, <, !=
- ✅ Numeric and string state matching
- ✅ Safe fallback to visible if entity unavailable
- ✅ Frontend filtering in child card
- ✅ State attributes properly exposed
- ✅ Configuration persists across edit workflow steps
- ✅ Works with both specific_days and recurring schedules

---

## 📋 Technical Details

### Files Modified
- `custom_components/taskmate/config_flow.py`
  - Fixed Step 2 methods to use `_edited_chore` instead of `_chore_step1_data`
  - Added `_edited_chore` initialization in `__init__`
  - Enhanced debug logging for visibility fields
  
- `custom_components/taskmate/sensor.py`
  - Added visibility fields to chore state attributes dictionary

### Compatibility
- ✅ Fully backward compatible with existing chore configurations
- ✅ Chores without visibility settings work unchanged
- ✅ No breaking changes to API or data format

---

## 🧪 Testing Recommendations

1. **Edit Existing Chore with Visibility**
   - Add/edit visibility settings in Step 1
   - Proceed to Step 2 (schedule selection)
   - Submit Step 2
   - Verify visibility fields persist in Developer Tools > States

2. **Create New Chore with Visibility**
   - Set visibility entity and operator
   - Complete both steps
   - Verify chore appears/disappears based on entity state

3. **Frontend Filtering**
   - Set visibility condition that doesn't match
   - Verify chore doesn't appear on child card
   - Change entity state to match condition
   - Verify chore appears (after ~30 second refresh)

---

## 📝 Known Limitations

- Visibility checks update every 30 seconds (coordinator refresh interval)
- Numeric comparisons require valid float conversion; invalid values fall back to string matching
- Visibility only affects card display; it doesn't prevent API completion of hidden chores
- Multiple visibility conditions per chore not yet supported

---

## 🚀 Next Steps

- Consider adding AND/OR logic for multiple visibility conditions
- Evaluate instant visibility updates vs. 30-second refresh interval
- Gather user feedback on common use cases and refinements

---

## 📦 What's Included

- Core integration with dynamic visibility logic (complete and tested)
- Config flow UI for setting up visibility rules (fully functional)
- 14 Lovelace cards (unchanged from previous releases)
- Full translation support (English, French)
- Comprehensive test suite

---

## 💬 Feedback & Reporting Issues

Found a bug or have a feature request? Open an issue on GitHub:  
👉 https://github.com/tempus2016/taskmate/issues

---

## 📄 License

TaskMate is licensed under the MIT License.

---

**Thank you for testing TaskMate 2.4.0-beta7!**

Your feedback helps us make TaskMate better. Please report any issues or suggestions.
