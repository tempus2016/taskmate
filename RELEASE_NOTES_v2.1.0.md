# TaskMate v2.1.0

## What's New

### Penalty System

The flip side of rewards — deduct points for unwanted behaviour without having to guess an amount each time.

Create named penalties (e.g. **"Not going to bed"**, **"Too much screen time"**, **"Talking back"**) with a fixed point deduction, then apply them to a child with a single tap. The deduction is logged in the activity feed so you always have a record.

**New `taskmate-penalties-card`**

- Child selector tabs at the top (hidden when there's only one child)
- Each penalty shows its icon, name, and point cost in a red badge
- Tap **Apply** → points deducted instantly, tile flashes red, toast confirms the action
- Toggle **edit mode** (pencil icon) to add, rename, or delete penalties

**4 new services for automation / scripting**

| Service | Description |
|---------|-------------|
| `taskmate.add_penalty` | Create a new penalty definition |
| `taskmate.update_penalty` | Update an existing penalty's name, points, or icon |
| `taskmate.remove_penalty` | Delete a penalty definition |
| `taskmate.apply_penalty` | Apply a penalty to a child (deducts points immediately) |

Example:

```yaml
service: taskmate.apply_penalty
data:
  penalty_id: abc12345
  child_id: a8c8376a
```

---

## Bug Fixes

- **Crash deleting a chore** — The config flow called a non-existent method (`async_delete_chore`) instead of the correct `async_remove_chore`. Deleting a chore from Settings now works correctly.

- **Crash when settings contain invalid values** — If a setting like `weekend_multiplier` or `perfect_week_bonus` was somehow saved as a non-numeric string, `float()`/`int()` would throw and take the entire sensor offline. These conversions now fall back to their defaults gracefully.

- **Crash in chore availability check** — `is_chore_available_for_child` caught `ValueError` when parsing a stored date string, but not `TypeError`. If the stored value was `None` or a non-string, slicing it raised an unhandled `TypeError`. Fixed to catch both.

- **Reward rejection bypassed storage API** — `async_reject_reward` was directly writing to `storage._data["reward_claims"]` instead of going through the storage layer. Added `remove_reward_claim()` to `TaskMateStorage` and updated the coordinator to use it.

- **Double dict lookup for child names** — A fragile `a and b or c` pattern was used to look up the same child dict key twice in the sensor. Replaced with a clean single lookup.

---

## Upgrade Notes

No migration needed. Penalties are stored in a new `penalties` key in the TaskMate data store — existing data is untouched.

After upgrading, hard-refresh your browser (**Cmd+Shift+R** / **Ctrl+Shift+R**) to load the new card JavaScript.
