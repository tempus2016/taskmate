# Praise Notes

Approve with a short message the child sees on their card: the mirror of a [reject reason](Reject-Reasons.md).

---

## Sending One

- **Panel:** in the approval queue, tap **💬** beside a chore, type a note (up to 120 characters) or pick a quick chip — *👏 Well done!*, *🌟 Super effort*, *💪 Proud of you*, *🙏 Thank you!* — then **Approve**.
- **[Approvals card](Approvals-Card.md):** open the review sheet (✎) beside a chore; the praise box and chips are under the points.
- **Service:** `taskmate.approve_chore` with `note`, or the `taskmate/approve_chore` WebSocket command with `note`.

The note is stored on the completion with the name of the Home Assistant user who approved it.

---

## On the Card

The child's [card](Dashboard-Cards.md#child-card) shows today's notes as strips above the chores: *"💬 Dad: Great job on the bathroom! — Clean bathroom"*. With no name to show (an automation, say) it reads *"Grown-up"*. The newest three show, until midnight. Hide them on one card with `show_praise: false`.

---

## For Automations

`taskmate_chore_approved` includes `praise_note` when there is one. The overview sensor's per-child summary carries `praise`: `[{chore_name, note, by}]`.

---

## Related

- [Reject Reasons](Reject-Reasons.md)
- [Quality Ratings](Quality-Ratings.md)
