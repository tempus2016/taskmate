# Reward Limits, Gifts, Ratings, Pictures and Vouchers

A handful of extras for rewards. Each one is optional and stays out of the way until you use it.

---

## Limit Per Child

"Once a week each", so one child can't claim every movie pick.

In the reward dialog, open **Limit per child** and set **Claims per child** and **Per** (day, week from Monday, or month). `0` means no limit.

- Waiting and approved claims made in the current day, week or month count. A rejected claim doesn't.
- A gift counts for the child who gets it, not the one who paid.
- Claiming past the limit is refused with a clear message, e.g. *"Vaiha can have 'Pick the movie' once a week. It's available again on 2026-10-26"*.
- On the rewards card the child sees **Again on Monday** and a greyed-out claim button.

The reward's `limit` (`count`, `period`) and `limit_reached` (`{child_id: date it opens again}`) are on the rewards sensor, only for rewards that have a limit.

---

## Reward Pictures

Upload a photo for a reward instead of only an icon: great for children who can't read yet. In the reward dialog, **Picture → Upload** (JPEG, PNG or WebP, resized to 512 px). **Remove** goes back to the icon.

The picture shows on the rewards card and on the child card's savings forecast; anywhere there's no picture the icon is used. Pictures are stored and served like [chore pictures](Chores.md), and the file is deleted when its picture is replaced, or 7 days after the reward is deleted (until then [Recently Deleted](Recently-Deleted.md) can bring it back, picture included).

---

## Buying a Reward for a Sibling

Switch on **Settings → Gifts between children → Children can buy rewards for each other**.

When a child claims a reward on the rewards card, the confirm dialog asks **Who is it for?** — *Me* or a brother or sister. Then:

- **The buyer pays.** The claim goes through the normal approval, and the [spending cap](Rewards.md#per-period-spending-cap-v400) applies to the buyer.
- **The recipient gets it.** Their card shows *"Vaiha bought you Ice cream! Waiting for a grown-up to hand it over"* while it waits for approval, and the [owed list](Reward-Fulfilment.md) and **Got it!** belong to the recipient until it's handed over.
- **Screen-time** minutes go onto the recipient's [balance](Screen-Time-Bank.md), and a [timed unlock](Timed-Unlock-Rewards.md) is started for them.
- The recipient must be allowed the reward (its **Assigned to** list), and must be a child: grown-up profiles can't be picked.
- **Shared jackpots**, **savings-jar** rewards and **streak freezes** can't be gifted. Their points or tokens belong to the child who saved them.

Approval lists show the recipient (🎁 Malia). The service is `taskmate.claim_reward` with an optional `recipient_id`.

---

## Rate the Reward

Once a reward has been handed over (or approved, if [reward fulfilment](Reward-Fulfilment.md) is off) the child who had it sees *"How was Cinema trip? ☆☆☆"* on their card for three days, and can give it 1 to 3 stars. A rating can't be changed.

The panel's **Rewards** page shows a **Reward ratings** table: each reward's average stars, how many times it's been claimed, and *never claimed · retire?* for rewards nobody has bought.

Service: `taskmate.rate_reward`. Event: `taskmate_reward_rated`.

---

## "At This Rate" Savings Forecast

The child card shows the cheapest reward the child can't afford yet, with a forecast: *"Lego set · 842/1000 — At your pace (~45 a day) you'll have it on Thursday"*.

- The pace is the child's average over the last 14 days: approved chore points plus bonuses and other additions. Refunds and gifts from a sibling don't count.
- Jackpots, savings-jar rewards, streak freezes and rewards that aren't available are skipped.
- It's hidden when the child is earning next to nothing, or the reward is more than 60 days away.

The pace is on `sensor.taskmate_overview` as the child's `earn_rate`, only when it's above zero.

---

## Printable Vouchers

An approved reward can be printed as a voucher to hand over: the reward, who it's for (and who it's from, for a gift), what it cost and when, and a *Signed: ____* line.

Use **🖨️ Print voucher** next to a reward in the **Rewards owed** list on the Today page, or the 🖨️ next to a claimed reward in the activity timeline. The voucher opens in a new tab ready to print; allow pop-ups for Home Assistant if nothing opens.

Like the [printable weekly chart](Printable-Weekly-Chart.md), it comes from an admin-only WebSocket command, `taskmate/print/reward_voucher`, as a standalone HTML page with no external files.
