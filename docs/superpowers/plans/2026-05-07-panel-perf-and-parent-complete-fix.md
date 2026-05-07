# Admin Panel Render Performance + Parent-Complete Child Card Fix

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix parent-complete not reflecting on child cards, and eliminate the 1322ms click handler violation in the admin panel by switching to zone-based partial DOM updates.

**Architecture:** The child card bug is a filter condition that excludes `"__parent__"` completions — three one-liner fixes. The panel performance work restructures `_render()` to create a stable DOM shell on first render, then only update named zones whose content has changed, and caches the ~1170-line CSS block so it's never regenerated.

**Tech Stack:** Vanilla JavaScript (HTMLElement for panel, LitElement for child card), Home Assistant frontend APIs.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `custom_components/taskmate/www/taskmate-child-card.js` | Modify (3 lines) | Include `__parent__` completions in filter conditions |
| `custom_components/taskmate/www/taskmate-panel.js` | Modify (`_render`, `_bindHaPickers`, constructor) | Zone-based partial DOM updates, cached styles |

---

### Task 1: Fix parent-complete visibility on child card

**Files:**
- Modify: `custom_components/taskmate/www/taskmate-child-card.js:2113-2115` (main completion count)
- Modify: `custom_components/taskmate/www/taskmate-child-card.js:1755-1757` (dynamic assignment pool count)
- Modify: `custom_components/taskmate/www/taskmate-child-card.js:2406-2408` (bonus subtask parent-done check)

- [ ] **Step 1: Update `_renderChoreCard` completion filter**

In `custom_components/taskmate/www/taskmate-child-card.js`, change line 2113-2115 from:

```javascript
    const childCompletionsToday = todaysCompletions.filter(
      (comp) => comp.chore_id === chore.id && comp.child_id === child.id && !comp.bonus_subtask_id
    );
```

to:

```javascript
    const childCompletionsToday = todaysCompletions.filter(
      (comp) => comp.chore_id === chore.id && (comp.child_id === child.id || comp.child_id === "__parent__") && !comp.bonus_subtask_id
    );
```

- [ ] **Step 2: Update `_filterAndSortChores` dynamic assignment pool filter**

In the same file, change line 1755-1757 from:

```javascript
          const poolCompletionsToday = allTodayCompletions.filter(
            comp => comp.chore_id === chore.id && poolSet.has(String(comp.child_id))
          ).length;
```

to:

```javascript
          const poolCompletionsToday = allTodayCompletions.filter(
            comp => comp.chore_id === chore.id && (poolSet.has(String(comp.child_id)) || comp.child_id === "__parent__")
          ).length;
```

- [ ] **Step 3: Update `_renderBonusSubtasks` parent-done filter**

In the same file, change line 2406-2408 from:

```javascript
    const parentCompletions = todaysCompletions.filter(
      c => c.chore_id === chore.id && c.child_id === child.id && !c.bonus_subtask_id
    );
```

to:

```javascript
    const parentCompletions = todaysCompletions.filter(
      c => c.chore_id === chore.id && (c.child_id === child.id || c.child_id === "__parent__") && !c.bonus_subtask_id
    );
```

- [ ] **Step 4: Commit the child card fix**

```bash
git add custom_components/taskmate/www/taskmate-child-card.js
git commit -m "fix: include __parent__ completions in child card filters

Child card completion filters only matched the child's own ID,
so parent-complete chores never showed as done on the card."
```

---

### Task 2: Cache styles and add shell structure to `_render()`

**Files:**
- Modify: `custom_components/taskmate/www/taskmate-panel.js:120-151` (constructor — add new properties)
- Modify: `custom_components/taskmate/www/taskmate-panel.js:1150-1190` (`_render()` — zone-based logic)

- [ ] **Step 1: Add zone-tracking properties to constructor**

In `custom_components/taskmate/www/taskmate-panel.js`, add three new properties inside the constructor after line 137 (`this._rendered = false;`):

```javascript
    this._shellReady = false;
    this._zoneCache = {};
    this._cachedStyles = null;
```

Insert these three lines immediately after `this._rendered = false;` (line 137) and before `this._onFocusIn = this._onFocusIn.bind(this);` (line 138).

- [ ] **Step 2: Replace `_render()` with zone-based implementation**

Replace the entire `_render()` method (lines 1151–1190) with the following:

```javascript
  _render() {
    this._rendered = true;

    if (!this._shellReady) {
      if (!this._cachedStyles) {
        this._cachedStyles = this._styles();
      }
      const existingToast = this.querySelector(".tm-toast");
      this.innerHTML = `
        ${this._cachedStyles}
        <div class="tm-shell">
          <div data-zone="sidebar">${this._sidebar()}</div>
          <div class="tm-main">
            <div data-zone="topbar">${this._topbar()}</div>
            <div data-zone="mtabs">${this._mobileTabs()}</div>
            <div data-zone="approval">${this._approvalBanner()}</div>
            <div class="tm-body">
              <div class="tm-body-inner" data-zone="body">${this._renderBody()}</div>
            </div>
          </div>
          <div data-zone="dialog">${this._dialog ? this._renderDialog() : ""}</div>
          <div data-zone="tpl">${this._renderSaveTemplateDialog()}</div>
        </div>
      `;
      if (existingToast) this.appendChild(existingToast);
      this._shellReady = true;
      this._zoneCache = {};
      this._bindHaPickers();
      return;
    }

    const zones = {
      sidebar:  this._sidebar(),
      topbar:   this._topbar(),
      mtabs:    this._mobileTabs(),
      approval: this._approvalBanner(),
      body:     this._renderBody(),
      dialog:   this._dialog ? this._renderDialog() : "",
      tpl:      this._renderSaveTemplateDialog(),
    };

    const dialogZone = this.querySelector('[data-zone="dialog"]');
    let savedScroll = 0;
    if (dialogZone) {
      const dialogBody = dialogZone.querySelector(".tm-dialog-body");
      savedScroll = dialogBody ? dialogBody.scrollTop : 0;
    }

    if (this._dialog) {
      const openSet = this._dialog._openAdvanced instanceof Set ? this._dialog._openAdvanced : new Set();
      this.querySelectorAll("details.tm-advanced[data-section]").forEach(el => {
        const key = el.dataset.section;
        if (!key) return;
        if (el.open) openSet.add(key); else openSet.delete(key);
      });
      this._dialog._openAdvanced = openSet;
    }

    let anyChanged = false;
    for (const [name, html] of Object.entries(zones)) {
      if (this._zoneCache[name] === html) continue;
      this._zoneCache[name] = html;
      const el = this.querySelector(`[data-zone="${name}"]`);
      if (!el) { this._shellReady = false; this._render(); return; }
      el.innerHTML = html;
      anyChanged = true;
    }

    if (anyChanged) {
      this._bindHaPickers();
    }

    if (savedScroll) {
      const newBody = dialogZone && dialogZone.querySelector(".tm-dialog-body");
      if (newBody) newBody.scrollTop = savedScroll;
    }
  }
```

- [ ] **Step 3: Run existing tests to verify nothing is broken**

Run: `cd /home/claude/workspace/taskmate && python -m pytest tests/ -x -q`

Expected: All tests pass (the panel is frontend JS; Python tests cover the backend which is unchanged).

- [ ] **Step 4: Commit the panel performance work**

```bash
git add custom_components/taskmate/www/taskmate-panel.js
git commit -m "perf: zone-based partial DOM updates for admin panel

Cache the ~1170-line CSS block and only replace zones whose
content has changed instead of rebuilding the entire innerHTML
on every click."
```

---

### Task 3: Integration verification

- [ ] **Step 1: Verify panel shell creation**

Open Home Assistant at `:8123/taskmate-admin` in a browser. Inspect the DOM and confirm:
- A single `<style>` element exists inside `<taskmate-panel>` (not regenerated on each click)
- `data-zone="sidebar"`, `data-zone="body"`, `data-zone="dialog"` etc. wrapper elements exist
- Clicking between tabs updates only the changed zones (sidebar, topbar, mtabs, body) — the `<style>` and shell `<div class="tm-shell">` persist

- [ ] **Step 2: Verify click performance**

Open DevTools Console. Click between tabs, open/close dialogs, save a chore. Confirm:
- No more `[Violation] 'click' handler took >Xms` warnings in the console
- All tab content renders correctly
- Dialogs open/close with correct content
- Toast notifications still appear and auto-dismiss
- Dialog scroll position is preserved when editing form fields
- `<details class="tm-advanced">` sections remember open/closed state across renders

- [ ] **Step 3: Verify parent-complete on child card**

In the admin panel Chores tab, click "Parent Did It" on a chore. Then check:
- The child's Lovelace card shows the chore as completed (green/checked state)
- For chores with bonus subtasks: the bonus subtask rows appear after parent-complete
- For alternating/random assignment chores: the chore disappears from all pool children's cards

- [ ] **Step 4: Verify search, entity pickers, and HA pickers still work**

In the admin panel:
- Type in the search/filter box — body zone updates, results filter live
- Open a chore dialog with an entity picker — picker dropdown works
- Open a dialog with `ha-icon-picker` — icon selection works
- Drag-to-reorder chores in the reorder dialog — drag and drop works

- [ ] **Step 5: Final commit (if any touch-ups needed)**

If any adjustments were made during verification:

```bash
git add -u
git commit -m "fix: address issues found during integration testing"
```
