# Troubleshooting

## Cards Show "Custom element doesn't exist"

The Lovelace resources haven't loaded yet.

**Fix:**
1. Hard refresh the browser: **Cmd+Shift+R** (Mac) or **Ctrl+Shift+R** (Windows/Linux)
2. If that doesn't work, check **Settings → Dashboards → Resources** — the `/taskmate/*.js` entries should be listed
3. If the resources are missing, restart Home Assistant — they are registered automatically on startup

---

## Cards Show "Entity not found: sensor.taskmate_overview"

The entity name is wrong or the integration isn't loaded.

**Fix:**
1. Go to **Developer Tools → States** and search for `taskmate` — verify the entity exists
2. Make sure you're using `sensor.taskmate_overview` (not `sensor.taskmate_pending_approvals`)
3. If the entity doesn't exist, check **Settings → Devices & Services** — is TaskMate listed?
4. If TaskMate is listed but entities are missing, try reloading the integration

---

## Cards Render as Empty Boxes

JavaScript is failing to parse. Usually caused by a corrupted or outdated JS file.

**Fix:**
1. Open browser DevTools (F12) → Console tab — look for errors mentioning `taskmate-*.js`
2. Check the error message — `Unexpected token '}'` indicates a JS syntax error
3. Hard refresh after deploying new card files
4. Verify the file sizes are correct — files under ~1KB are likely corrupted

---

## Child Card Blank on an Older iPhone or iPad

On iOS 15 (Safari 16.3 and older, including the Home Assistant companion app on those devices), the Child Card showed nothing from v6.0.0 to v6.1.0, while the other cards still worked.

**Fix:** update TaskMate to **v6.2.0** or later, then hard refresh or restart the companion app.

---

## Resources Keep Disappearing After Restart

This was a known issue that has been fixed across two releases:

**v1.1.2** — The resource manager was accidentally deleting entries it couldn't match. The delete logic was removed entirely — the manager now only ever adds or updates, never deletes.

**v1.1.6** — A deeper root cause was identified. `ResourceStorageCollection` is lazy and doesn't load from disk until forced. TaskMate was reading resources before the storage had loaded, getting an empty list, writing all 13 entries, and then having them wiped when Lovelace loaded its own storage file shortly after. The fix forces the storage to load before TaskMate touches anything — the same approach used by the WebRTC and Browser Mod integrations.

**Fix:** Update to v1.1.6 or later. If you are already on v1.1.6+ and resources are still disappearing, check `Settings → System → Logs` (filter by `taskmate`) for error messages from the resource manager.

---

## Chore Description Not Showing

**Checklist:**
1. The chore must have a description set — open the **TaskMate** panel → **Chores**, edit the chore, check the Description field
2. **Show chore description** must be enabled in the child card editor (it's off by default)

---

## Points Not Updating After Completing a Chore

If the chore has **Requires Approval** turned on:
- Points are held as "pending" until a parent approves
- The child card header shows a "Pending" section with the held points
- Approve the completion from the Parent Dashboard card or Approvals card

If the chore does **not** require approval and points still aren't updating:
- Check Developer Tools → States → `sensor.taskmate_overview` → `children` array — is the child's `points` value changing?
- The sensor updates every 30 seconds — wait a moment and refresh

---

## Streak Not Incrementing

**Things to check:**
- Streaks are updated at **midnight** — if you complete chores and check before midnight, the streak won't have incremented yet
- The streak increments the next day when the overnight check confirms yesterday had a completion
- If **Streak Reset Mode** is `reset` and a day was missed, the streak resets to 0

---

## Streak Reset to Zero Unexpectedly

- Check the **Streak Reset Mode** in Settings — if set to `reset`, any missed day resets the streak
- Change to `pause` if you want streaks to be preserved across missed days
- Streaks are based on the child's `last_completion_date` compared to today's date in the HA timezone — timezone issues can cause false resets

---

## Wrong Timezone on Chore Completions

TaskMate uses the Home Assistant configured timezone for all date comparisons.

**Fix:**
1. Check your HA timezone: **Settings → System → General → Time Zone**
2. Ensure it matches your actual timezone
3. The `today_day_of_week` attribute on `sensor.taskmate_overview` shows the current day in HA timezone — verify it's correct

---

## Reward Cost Seems Wrong

All reward costs are fixed values set by the parent — there is no dynamic calculation.

**Checklist:**
1. Open the **TaskMate** panel → **Rewards** → edit the reward → check the **Points cost** field
2. Verify the child has enough points — check `sensor.taskmate_overview` → `children` → `points` for that child
3. If the child has a pending reward claim, those points are committed and shown as `committed_points` — they can't be used for another claim until the first is approved or rejected

---

## Fart Sounds Not Playing

**Checklist:**
1. The `.mp3` files must be in `/config/www/taskmate/`
2. Files must be named exactly `fart1.mp3` through `fart10.mp3`
3. Try `taskmate.preview_sound` with `sound: fart1` in Developer Tools to test
4. Browser autoplay policies may block audio until the user has interacted with the page — tap something first

---

## Integration Fails to Load

**Check the logs:**

Settings → System → Logs → search for `taskmate`

Common errors:
- `ImportError` — a dependency is missing. Try restarting HA or reinstalling the integration
- `ValueError` in storage — storage data may be corrupted. Check `/config/.storage/taskmate.storage.*`
- `Lovelace not available` — the lovelace integration hasn't loaded yet. Usually resolves on next restart

---

## Getting More Debug Information

Enable debug logging for TaskMate:

```yaml
# configuration.yaml
logger:
  logs:
    custom_components.taskmate: debug
```

Restart HA and check **Settings → System → Logs** for detailed output from the coordinator, storage, and resource manager.

---

## Notifications Not Working

**Persistent notifications not appearing:**
- Check **Settings → System → Logs** for `TaskMate: failed to send notification` errors
- Verify the chore has **Requires Approval** turned on — notifications only fire for approval-required chores
- Chores that auto-approve (Requires Approval = off) never trigger a notification

**Push notifications not arriving:**
- Go to the **TaskMate** panel → **Settings** and verify the Notification Service is set correctly
- The format must be `notify.service_name` e.g. `notify.mobile_app_johns_phone`
- Test the service directly: **Developer Tools → Services** → call `notify.mobile_app_johns_phone` with a test message
- If you want to notify multiple people, create a notify group in `configuration.yaml` and use `notify.group_name`

---

## Recurring Chore Not Appearing / Still Locked

**Chore shows as dimmed or hidden after completing it:**
- This is correct behaviour for recurring chores — the window hasn't reset yet
- The `recurrence_done_mode` on the child card controls whether it's dimmed or hidden
- Check `sensor.taskmate_overview` → `chores` → find the chore → check `is_available` for your child's ID

**Chore never becomes available:**
- If **Wait for First Scheduled Occurrence** is set, the chore is locked until the first scheduled day arrives
- For Every 2 Days with a future start date, the chore is locked until that date

**Window reset earlier than expected:**
- Check if the chore was completed and then undone — undo restores the previous completion as the anchor
- The `history_days` setting does not affect recurrence — the `last_completed` store is separate and never pruned

---

## Timed Task Timer Not Starting

**Checklist:**
1. The chore must have `task_type` set to `timed` — edit the chore and verify
2. If a daily cap is set, check whether the child has already reached it today
3. Check for an existing stale session — if one exists from a previous day, it should be auto-cleaned at midnight
4. Verify the chore is assigned to the child and available today

---

## Timed Task Points Seem Wrong

Points are calculated as `floor(total_seconds / (rate_minutes × 60)) × rate_points`. Partial windows are dropped, not rounded.

**Example:** 23 minutes at 10 pts / 5 min = `floor(23/5) × 10 = 40 points` (not 46).

If the daily cap is set, the duration is clamped before calculation.

---

## Task Group Not Coordinating Assignments

**Checklist:**
1. Task groups only work with rotation modes (`alternating`, `random`, `balanced`) — chores in `everyone` mode are unaffected
2. For sticky groups, the first chore in `chore_ids` is the leader — check the order
3. If the leader's assigned child is not in a follower's pool, the follower falls back to independent rotation
4. Verify the group exists — check `sensor.taskmate_incentives` → `task_groups`

---

## Bonus Subtask Not Appearing

**Checklist:**
1. The parent chore must be completed by the same child today before subtasks unlock
2. Verify the chore has bonus subtasks configured — check `sensor.taskmate_chores` → find the chore → `bonus_subtasks`
3. Each subtask can only be completed once per child per day

---

## Admin Panel Not Showing in Sidebar

**Checklist:**
1. The panel requires an **admin** HA user — non-admin users will not see it
2. Try restarting Home Assistant — the panel is registered on integration setup
3. Check logs for errors related to `panel_custom` or `taskmate-panel`

---

## "State attributes … exceed maximum size of 16384 bytes" in the Log

```
WARNING (Recorder) [homeassistant.components.recorder.db_schema] State attributes
for sensor.taskmate_activity exceed maximum size of 16384 bytes. This can cause
database performance issues; Attributes will not be stored
```

**Fixed in v5.3.0 — upgrade.** TaskMate's sensors carry large lists (recent
completions, pending approvals, the chore catalogue). Home Assistant's recorder
refuses to store any attribute payload over 16 KB and, when it hits that limit,
discards the entity's *entire* attribute set for that state. Larger families hit
it easily, most visibly right after approving a batch of chores.

From v5.3.0 those lists are declared unrecorded, so the recorder skips them and
the warning stops. Nothing you use changes — the lists are still on the live
state, so cards, templates and automations are unaffected. See
[Attributes and the recorder](Sensor-Attributes.md#attributes-and-the-recorder-v530).

If you still see the warning after upgrading, check the entity named in the
message: if it is not a `sensor.taskmate_*` entity, it belongs to a different
integration.

---

## "image_url must be a TaskMate image URL" When Saving a Chore

```
Error handling message: image_url must be a TaskMate image URL for dictionary
value @ data['image_url']. Got '/api/taskmate/image/<name>.jpg?authSig=eyJhbGciOi…'
(invalid_format)
```

**Fixed in v5.4.1 — upgrade.** Adding a picture to a chore worked, but every
later edit of that chore was rejected with this error and the change was lost,
so the chore looked permanently uneditable.

TaskMate signs chore image URLs before sending them to the admin panel, because
a browser does not attach the Home Assistant bearer token to a plain `<img>`
request — an unsigned URL would return 401 and the picture would never appear.
The chore editor filled its form from that state and sent the signed value back
on save, while the save-side check only accepted the bare
`/api/taskmate/image/<name>.jpg` form. Uploading a new image succeeded because
the upload response is unsigned; only re-saving an existing one failed.

From v5.4.1 the signature is stripped and the bare path validated when the chore
is saved, so only the canonical URL is stored. Nothing needs re-uploading —
existing chores and their images are unaffected, and a chore whose edits were
failing will simply save after upgrading.

---

## Rewards Card Disappears When a Child Claims a Reward

The rewards card renders as an empty space — no header, no rewards, nothing —
from the moment a child claims a reward until a parent approves or rejects it.
Approving the claim brings the whole card back as if nothing had happened. An
approvals card set to a single child goes blank at the same time, and the parent
dashboard's pending total reads `NaN`.

**Fixed in v5.4.2 — upgrade.** Nothing in your configuration causes this and
nothing needs changing; in particular it is unrelated to renaming your points,
which several people reasonably suspected because the two often coincide.

Two sensors were publishing different data under one attribute name.
`sensor.taskmate_rewards` uses `pending_reward_claims` for the *list* of pending
claims, while `sensor.taskmate_pending_approvals` used the same name for a plain
*count*. Cards read attributes through a resolver that merges the companion
sensors over the primary one, and the approvals sensor merges last — so the
number replaced the list. The cards then filtered a number, the render threw,
and Home Assistant leaves a card whose render fails as blank space.

It only showed up once something was actually pending: with no claims the count
is `0`, which is falsy, so the cards' own fallback quietly substituted an empty
list and everything worked. Present from **v5.2.0**, when the companion sensor
id was corrected and the colliding attribute started being merged at all.

From v5.4.2 the resolver refuses to merge the approvals sensor's three count
attributes, and the cards coerce the value to a list before using it. The counts
are unchanged on `sensor.taskmate_pending_approvals` itself and still work in
templates and automations.

---

## Reporting a Bug

If you've confirmed it's a TaskMate bug, open an issue at:
**https://github.com/tempus2016/taskmate/issues**

Include:
- TaskMate version (visible in Settings → Devices & Services → TaskMate)
- Home Assistant version
- Relevant log output with debug logging enabled
- Steps to reproduce
