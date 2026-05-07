# Admin Panel Render Performance + Parent-Complete Child Card Bug

**Date:** 2026-05-07
**Scope:** `taskmate-panel.js` (performance), `taskmate-child-card.js` (bug fix)

---

## Problem Statement

Two issues in the TaskMate admin panel and child card:

1. **Slow click handlers (1322ms):** Every click in the admin panel triggers `_render()`, which does a full `this.innerHTML` replacement of the entire panel. This includes regenerating ~1170 lines of CSS from `_styles()` on every call. The browser must parse all HTML/CSS, destroy all DOM nodes, rebuild them, and re-layout — consistently exceeding the 50ms budget Chrome flags as a violation.

2. **Parent-complete not reflected on child card:** When an admin clicks "Parent Did It" in the panel, the chore is not shown as completed on the child's Lovelace card. The backend correctly creates a completion with `child_id: "__parent__"` and updates `last_completed` per child, but the child card filters completions by `comp.child_id === child.id` and never matches `"__parent__"`.

---

## Issue 1: Parent-Complete Bug Fix

### Root Cause

`taskmate-child-card.js` has three locations that filter `todays_completions` by exact child ID match, excluding `"__parent__"` completions:

| Location | Line | Purpose |
|----------|------|---------|
| `_renderChoreCard` | 2113 | Main completion count — determines done/checkmark state |
| `_renderBonusSubtasks` | 2406 | Parent chore done check — controls bonus subtask visibility |
| `_filterAndSortChores` (dynamic assignment) | 1755 | Pool completion count for alternating/random chores |

### Fix

Add `|| comp.child_id === "__parent__"` to each filter condition.

**Line 2113 (`_renderChoreCard`):**
```javascript
// Before:
const childCompletionsToday = todaysCompletions.filter(
  (comp) => comp.chore_id === chore.id && comp.child_id === child.id && !comp.bonus_subtask_id
);

// After:
const childCompletionsToday = todaysCompletions.filter(
  (comp) => comp.chore_id === chore.id && (comp.child_id === child.id || comp.child_id === "__parent__") && !comp.bonus_subtask_id
);
```

**Line 2406 (`_renderBonusSubtasks`):**
```javascript
// Before:
const parentCompletions = todaysCompletions.filter(
  c => c.chore_id === chore.id && c.child_id === child.id && !c.bonus_subtask_id
);

// After:
const parentCompletions = todaysCompletions.filter(
  c => c.chore_id === chore.id && (c.child_id === child.id || c.child_id === "__parent__") && !c.bonus_subtask_id
);
```

**Line 1755 (`_filterAndSortChores` dynamic assignment pool check):**
```javascript
// Before:
const poolCompletionsToday = allTodayCompletions.filter(
  comp => comp.chore_id === chore.id && poolSet.has(String(comp.child_id))
).length;

// After:
const poolCompletionsToday = allTodayCompletions.filter(
  comp => comp.chore_id === chore.id && (poolSet.has(String(comp.child_id)) || comp.child_id === "__parent__")
).length;
```

### Edge Cases

- **Timed chores:** Not affected. Timed chore rendering uses session state, not completions. The backend blocks parent-complete on one-shot chores but allows it on timed chores; however the timed card won't visually reflect it. This is acceptable — parent-complete on a timed chore is an unusual operation.
- **Undo after parent-complete:** The child card's undo handler searches `childCompletionsToday` for the most recent completion. With the fix, it will find `"__parent__"` completions. The undo service call uses the completion ID, which is valid regardless of who created it — but undo of a parent-complete should probably not be available to the child. This is a pre-existing design question, not introduced by this fix.
- **Bonus subtask availability after parent-complete:** With the fix, bonus subtasks will appear after a parent-complete. Since the parent-complete awards zero points, the child could then claim bonus points. This matches the existing behaviour for regular completions where a child completes the main chore — bonus subtasks become available.

---

## Issue 2: Admin Panel Render Performance

### Current Architecture

`taskmate-panel.js` (4322 lines) uses a single `_render()` method that:
1. Saves dialog scroll position and open `<details>` state
2. Sets `this.innerHTML` to a concatenated string of `_styles()` + `_sidebar()` + `_topbar()` + `_mobileTabs()` + `_approvalBanner()` + `_renderBody()` + `_renderDialog()` + `_renderSaveTemplateDialog()`
3. Re-appends any existing toast
4. Calls `_bindHaPickers()` to wire up HA custom elements

Every click handler — even tab switches and dialog opens — triggers a full rebuild.

### Zone-Based Architecture

#### First Render: Create Shell

On the first `_render()` call, inject the full shell structure with named zones:

```html
<style>…cached CSS…</style>
<div class="tm-shell">
  <div data-zone="sidebar">…</div>
  <div class="tm-main">
    <div data-zone="topbar">…</div>
    <div data-zone="mtabs">…</div>
    <div data-zone="approval">…</div>
    <div class="tm-body">
      <div class="tm-body-inner" data-zone="body">…</div>
    </div>
  </div>
</div>
<div data-zone="dialog">…</div>
<div data-zone="tpl">…</div>
```

The `<style>` element is created once and never regenerated. `_styles()` is called exactly once.

#### Subsequent Renders: Zone Updates

A helper `_zone(name)` retrieves zone elements by `data-zone` attribute. Each render:

1. Generate HTML strings for each zone (reusing existing methods unchanged)
2. Compare each zone's new HTML against a cached hash
3. Only update zones where content has changed via `zone.innerHTML = newContent`
4. Call `_bindHaPickers()` scoped to changed zones only

#### Zone Map

| Zone | Generator Method | Changes When |
|------|-----------------|--------------|
| `sidebar` | `_sidebar()` | Tab switch, state refresh |
| `topbar` | `_topbar()` | Tab switch |
| `mtabs` | `_mobileTabs()` | Tab switch |
| `approval` | `_approvalBanner()` | State refresh (pending approvals) |
| `body` | `_renderBody()` | Tab switch, state refresh, filter change |
| `dialog` | `_renderDialog()` or `""` | Dialog open/close/edit |
| `tpl` | `_renderSaveTemplateDialog()` | Template dialog state |

#### State Preservation

Existing preservation logic stays the same, scoped to the dialog zone:
- **Toast:** Appended to `this` (outside zones), untouched by zone updates
- **Dialog scroll:** Saved/restored when the dialog zone updates
- **`<details>` open state:** Snapshot before dialog zone update, restore after

#### Fallback

If the shell structure is missing (e.g. first render, or DOM was externally modified), fall back to the current full `innerHTML` rebuild. This makes the change safe — worst case, performance matches the current behaviour.

### Implementation Details

**New instance properties:**
- `_styleEl` — cached `<style>` element, created once
- `_shellReady` — boolean, true after first render creates the shell
- `_zoneHashes` — `Map<string, string>` storing content hashes per zone

**Modified methods:**
- `_render()` — split into shell-create (first call) and zone-update (subsequent calls)
- `_styles()` — called once, result cached in `_styleEl`
- `_bindHaPickers()` — accept optional root element to scope queries

**Unchanged methods:**
- `_sidebar()`, `_topbar()`, `_mobileTabs()`, `_approvalBanner()`, `_renderBody()`, `_renderDialog()`, `_renderSaveTemplateDialog()` — all untouched, still return HTML strings

### Expected Performance

| Scenario | Before | After |
|----------|--------|-------|
| Tab switch | ~1300ms (full rebuild + 1170-line CSS) | ~100-200ms (sidebar + topbar + body zones only) |
| Dialog open | ~1300ms | ~50-100ms (dialog zone only) |
| Save + state refresh | ~1300ms | ~200-300ms (all zones, no CSS) |
| Filter/search typing | ~1300ms per keystroke | ~100-200ms (body zone only) |

---

## Files Modified

| File | Change |
|------|--------|
| `custom_components/taskmate/www/taskmate-child-card.js` | 3 filter conditions updated for `__parent__` completions |
| `custom_components/taskmate/www/taskmate-panel.js` | `_render()` refactored to zone-based updates, `_styles()` cached |

---

## Testing

### Parent-Complete Bug
1. Open admin panel, go to Chores tab
2. Click "Parent Did It" on a chore assigned to a child
3. Verify the child's Lovelace card shows the chore as completed (green/checked)
4. Verify for chores with bonus subtasks: bonus subtasks appear after parent-complete
5. Verify for alternating/random assignment chores: chore disappears from all pool children
6. Verify undo still works from the child card after parent-complete

### Render Performance
1. Open admin panel, open browser DevTools Console
2. Switch between tabs — verify no "click handler took >Xms" violations
3. Open/close dialogs — verify responsiveness
4. Save a chore — verify toast appears promptly
5. Check that all existing functionality works: search/filter, drag-to-reorder, entity pickers, HA icon pickers, dialog scroll preservation, advanced details sections remember open/closed state
