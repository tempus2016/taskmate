# Guest Child Profiles

A visiting cousin gets a temporary child profile that expires on its own and stays out of the family leaderboard.

![Guests are ordinary children with an end date](images/panel-children.png)

Set **Guest** and an end date on a child (`is_guest`, `guest_expires_on`).

---

## Key Points

- **Guests don't compete.** They're excluded from the [leaderboard](Leaderboard-Seasons.md) — a cousin here for a week shouldn't win the month, and their leaving shouldn't read as a loss for everyone else.
- **No end date means no expiry.** You may not know how long the visit is, and silently archiving someone mid-stay would be worse than leaving the profile up a bit too long.
- **Expired guests are archived, not deleted.** The visit's completions stay in history, and next summer the same guest can be reactivated rather than rebuilt from scratch.
- **Promoting a guest to a family member** clears the end date and un-archives them. Someone who moves in shouldn't stay invisible.

---

## How Archiving Works

Archiving reuses the existing availability plumbing, so every chore and streak path already treats an archived guest as away — the same way [vacation mode](Vacation-Mode.md) does. There is no separate code path that could disagree with the rest of the integration about whether a child is present.

Archiving fires `taskmate_guest_archived`.

---

## A Typical Visit

1. Add the child, tick **Guest**, set the end date to the day they go home.
2. Assign them a couple of chores — they earn points like anyone else.
3. They stay off the leaderboard throughout.
4. On the end date they are archived automatically. Their history remains.
5. Next visit, reactivate the same profile.

---

## Related

- [Children](Children.md) — adding and managing children
- [Leaderboard Seasons](Leaderboard-Seasons.md) — which guests are excluded from
- [Vacation Mode](Vacation-Mode.md) — the same availability mechanism, for family members
- [Automations](Automations.md) — every TaskMate bus event
