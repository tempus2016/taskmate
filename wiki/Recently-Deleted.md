# Recently Deleted

**TaskMate panel → Settings → Recently deleted.** A deleted chore, reward or quest isn't gone straight away: it waits here for **7 days**, and **Restore** brings it back.

## Undo straight after deleting

Deleting a chore, reward or quest in the panel shows a message with an **Undo** button for a few seconds. Undo does the same as Restore.

## What comes back

Restore puts the item back under its **old id**, so its Home Assistant entities (the complete and claim buttons, for example) come back with the same entity ids, and their history lines up again.

| Item | Brought back with it |
|------|----------------------|
| Chore | Its completions, its recurrence history, weekly-target bonuses already paid, queued scheduled changes, its place in task groups, in the panel's chore order and in each child's chore order, and its picture. Its calendar events are published again. |
| Reward | Its claims (pending and approved), its place in the reward list, the children's savings towards it, and its picture. |
| Quest | Every child's progress through it. |

**Savings on a reward.** Deleting a reward refunds what the children had saved towards it. Restoring moves those points back into the jar, but only as far as each child still has them: a child who spent part of the refund gets back what they can cover.

**Not brought back:** a chore's open swap requests and teamwork joins, and its auctions (live auctions were called off and the bidders told when the chore went). Records for a child who has been deleted since are left out.

Restore refuses if something already uses the same id.

## After 7 days

Once a minute TaskMate forgets anything deleted more than 7 days ago. That is when a deleted chore's or reward's picture is removed from disk too (unless another chore or reward still shows it).

Chores removed with the Chores page's **bulk delete** are kept here too.

## Related

- [Admin Panel](Admin-Panel.md)
- [Managing Rewards](Managing-Rewards.md)
- [Backup & Restore](Backup-and-Restore.md) — for everything else
