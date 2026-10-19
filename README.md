<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/logo.svg" alt="TaskMate" width="180">
</p>

<h1 align="center">TaskMate</h1>

<p align="center">
  <strong>Turn chores into a game your kids actually want to play.</strong><br>
  A Home Assistant integration for family chore management, rewards, and streak tracking.
</p>

<p align="center">
  <a href="https://github.com/tempus2016/taskmate/releases"><img src="https://img.shields.io/github/v/release/tempus2016/taskmate" alt="Latest Release"></a>
  <a href="https://github.com/hacs/default"><img src="https://img.shields.io/badge/HACS-Default-41BDF5.svg" alt="HACS Default"></a>
  <a href="https://github.com/tempus2016/taskmate/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
  <img src="https://img.shields.io/badge/Home%20Assistant-2024.7+-blue" alt="HA Version">
  <a href="https://github.com/tempus2016/taskmate/releases"><img src="https://img.shields.io/github/downloads/tempus2016/taskmate/total" alt="Downloads"></a>
  <a href="https://community.home-assistant.io/t/taskmate-family-chore-rewards-integration-now-in-hacs-default/1023281"><img src="https://img.shields.io/badge/community-forum-41BDF5?logo=home-assistant&logoColor=white" alt="Community Forum"></a>
</p>

<p align="center">
  <a href="https://github.com/tempus2016/taskmate/actions/workflows/validate.yml"><img src="https://github.com/tempus2016/taskmate/actions/workflows/validate.yml/badge.svg" alt="HACS Validation"></a>
  <a href="https://github.com/tempus2016/taskmate/actions/workflows/hassfest.yaml"><img src="https://github.com/tempus2016/taskmate/actions/workflows/hassfest.yaml/badge.svg" alt="hassfest"></a>
  <a href="https://github.com/tempus2016/taskmate/actions/workflows/tests.yml"><img src="https://github.com/tempus2016/taskmate/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/tempus2016/taskmate/actions/workflows/lint.yml"><img src="https://github.com/tempus2016/taskmate/actions/workflows/lint.yml/badge.svg" alt="Lint"></a>
  <a href="https://github.com/tempus2016/taskmate/actions/workflows/data-checks.yml"><img src="https://github.com/tempus2016/taskmate/actions/workflows/data-checks.yml/badge.svg" alt="Data checks"></a>
  <a href="https://results.pre-commit.ci/latest/github/tempus2016/taskmate/main"><img src="https://results.pre-commit.ci/badge/github/tempus2016/taskmate/main.svg" alt="pre-commit.ci"></a>
</p>

<p align="center">
  <strong>📖 Full documentation lives at <a href="https://tempus2016.github.io/taskmate/">tempus2016.github.io/taskmate</a>.</strong>
</p>

---

## How it works

1. **Create chores** — assign them to children, set point values and schedules
2. **Kids complete chores** — tap the child card to tick them off, earn points, build streaks
3. **Parents approve** — chores marked "requires approval" land in a pending queue
4. **Kids claim rewards** — points are only deducted once a parent approves the claim

Everything is managed from the **TaskMate panel** in the Home Assistant sidebar, and surfaced on your dashboards through 31 Lovelace cards.

All data stays inside your Home Assistant instance. Nothing is sent to any external service.

<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/adminPanel.png" alt="TaskMate admin panel" width="700">
</p>

---

## Install

TaskMate is a **default HACS integration** — no custom repository needed.

1. Open **HACS** → search **"TaskMate"** → **Download**
2. **Restart Home Assistant**
3. **Settings → Devices & Services → Add Integration → TaskMate**
4. Pick your points name (Stars, Coins, Bucks…) and icon — that's the whole config flow

[![Open TaskMate in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tempus2016&repository=taskmate&category=integration)
&nbsp;
[![Add TaskMate integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=taskmate)

Requires **Home Assistant 2024.7+** and a current browser (Chrome, Firefox, Edge, or Safari).

For manual installation and the first-run walkthrough, see [Installation](https://tempus2016.github.io/taskmate/Installation/) and [Getting Started](https://tempus2016.github.io/taskmate/Getting-Started/).

---

## What you get

**Chores** — flexible [scheduling](https://tempus2016.github.io/taskmate/Chore-Scheduling/) (specific days, recurring down to every N days, rotation, first-come), [difficulty tiers](https://tempus2016.github.io/taskmate/Difficulty-Tiers/), [dependencies](https://tempus2016.github.io/taskmate/Chore-Dependencies/), [timed tasks](https://tempus2016.github.io/taskmate/Timed-Tasks/), [weekly targets](https://tempus2016.github.io/taskmate/Weekly-Targets/) for "three times this week, any day" with an optional bonus for hitting them, [photo proof](https://tempus2016.github.io/taskmate/Photo-Proof/), [open-ended chores](https://tempus2016.github.io/taskmate/Open-Ended-Chores/) the child describes and you price at approval, [teamwork chores](https://tempus2016.github.io/taskmate/Teamwork-Chores/) that need two or more children, [chore auctions](https://tempus2016.github.io/taskmate/Chore-Auctions/) where the lowest bid wins an unpopular job, a [bounty board](https://tempus2016.github.io/taskmate/Bounty-Board/) of one-off jobs any child can claim, [swaps](https://tempus2016.github.io/taskmate/Chore-Swaps/), [vacation mode](https://tempus2016.github.io/taskmate/Vacation-Mode/), and chores that appear or hide based on [HA entity state](https://tempus2016.github.io/taskmate/Dynamic-Chore-Visibility/) or [the weather](https://tempus2016.github.io/taskmate/Weather-Aware-Chores/). Children can [tap an NFC tag](https://tempus2016.github.io/taskmate/NFC-Tag-Completion/) to tick a chore off, and you can add, move and skip chores straight from [Home Assistant's calendar](https://tempus2016.github.io/taskmate/Two-Way-Calendar/). Missed ticking one? [Log a past job](https://tempus2016.github.io/taskmate/Logging-Past-Jobs/) on the day it was really done, up to a week back. Chores can carry an [estimated time](https://tempus2016.github.io/taskmate/Estimated-Minutes/) so children see how long is left, a [reference photo](https://tempus2016.github.io/taskmate/Reference-Photos/) of the job done well, or a [quantity](https://tempus2016.github.io/taskmate/Quantity-Chores/) that pays per item, and pending chores can [approve themselves](https://tempus2016.github.io/taskmate/Auto-Approve/) after a set number of hours.

**Points & rewards** — [fixed-cost rewards](https://tempus2016.github.io/taskmate/Rewards/) with a parent approval flow, [savings jars](https://tempus2016.github.io/taskmate/Pool-Mode-\(Savings-Jars\)/), a [wishlist](https://tempus2016.github.io/taskmate/Wishlist/) children save towards and family can pledge to, [bonuses](https://tempus2016.github.io/taskmate/Bonuses/) and [penalties](https://tempus2016.github.io/taskmate/Penalties/), [weekend multipliers and streak milestones](https://tempus2016.github.io/taskmate/Bonus-Points/), [1–3 star quality ratings](https://tempus2016.github.io/taskmate/Quality-Ratings/) that scale the points, [real-money allowance](https://tempus2016.github.io/taskmate/Allowance/), [shared family goals](https://tempus2016.github.io/taskmate/Family-Goals/), [timed device unlocks](https://tempus2016.github.io/taskmate/Timed-Unlock-Rewards/), and [time-locked rewards](https://tempus2016.github.io/taskmate/Time-Locked-Rewards/) that are only claimable on chosen days or between set hours. Children can buy tickets for a [raffle](https://tempus2016.github.io/taskmate/Raffles/) with their points, a [make-it-right penalty](https://tempus2016.github.io/taskmate/Make-It-Right-Penalties/) can be earned back by doing a chore, [boost windows](https://tempus2016.github.io/taskmate/Boost-Windows/) make chosen chores pay ×2 for a while (and can wake the wall tablet to say so), and [reward fulfilment](https://tempus2016.github.io/taskmate/Reward-Fulfilment/) keeps a redeemed reward on an owed list until somebody hands it over.

**Gamification** — a [virtual pet](https://tempus2016.github.io/taskmate/Virtual-Pets/) that hatches and grows as chores get done, [personal weekly goals](https://tempus2016.github.io/taskmate/Weekly-Goals/) with a bonus, [personal bests](https://tempus2016.github.io/taskmate/Personal-Bests/) every child can beat whatever their place on the leaderboard, [levels & XP](https://tempus2016.github.io/taskmate/Levels-and-XP/), [achievement badges](https://tempus2016.github.io/taskmate/Achievement-Badges/), [quests](https://tempus2016.github.io/taskmate/Quests/), [challenges](https://tempus2016.github.io/taskmate/Challenges/), [unlockable avatars](https://tempus2016.github.io/taskmate/Avatars/), [celebrations](https://tempus2016.github.io/taskmate/Celebrations/), [leaderboard seasons](https://tempus2016.github.io/taskmate/Leaderboard-Seasons/), [streak freezes](https://tempus2016.github.io/taskmate/Streak-Freezes/) that protect a streak through a missed day, [birthday mode](https://tempus2016.github.io/taskmate/Birthday-Mode/), [surprise inspections](https://tempus2016.github.io/taskmate/Surprise-Inspections/) with a bonus, and "Wrapped"-style [recaps](https://tempus2016.github.io/taskmate/Recaps/) on a schedule you choose.

**Parent tooling** — an [admin panel](https://tempus2016.github.io/taskmate/Admin-Panel/) with a Today home page and a [setup wizard](https://tempus2016.github.io/taskmate/Setup-Wizard/) that suggests chores by age, [ready-made dashboards](https://tempus2016.github.io/taskmate/Ready-Made-Dashboards/) for the kids, the parents and a wall tablet, [notifications](https://tempus2016.github.io/taskmate/Notifications/) in your Home Assistant language, with [quiet hours](https://tempus2016.github.io/taskmate/Quiet-Hours/), [reminder escalation](https://tempus2016.github.io/taskmate/Reminder-Escalation/) and [presence-aware reminders](https://tempus2016.github.io/taskmate/Presence-Aware-Reminders/) that wait until a child is home, [reject reasons](https://tempus2016.github.io/taskmate/Reject-Reasons/) the child can see, [multi-parent approval routing](https://tempus2016.github.io/taskmate/Multi-Parent-Approval-Routing/), a [weekly digest](https://tempus2016.github.io/taskmate/Weekly-Digest/), [insight reports](https://tempus2016.github.io/taskmate/Insights/) on fairness and friction, an [audit log](https://tempus2016.github.io/taskmate/Admin-Audit-Log/), [sick days](https://tempus2016.github.io/taskmate/Sick-Days/) that pause chores and protect streaks, [event entities](https://tempus2016.github.io/taskmate/Event-Entities/) for building automations in the UI editor, [Repairs issues and a diagnostics download](https://tempus2016.github.io/taskmate/Repairs-and-Diagnostics/), [adult profiles](https://tempus2016.github.io/taskmate/Adult-Profiles/) so parents can track their own chores without approving each other's, and [backup & restore](https://tempus2016.github.io/taskmate/Backup-and-Restore/).

**Made for kids** — a [sticker chart](https://tempus2016.github.io/taskmate/Sticker-Chart-Card/) where today's jobs are stickers to tap and stars fill up towards a reward, [Routine Mode](https://tempus2016.github.io/taskmate/Routine-Mode/) for guided morning and bedtime flows, [Pre-Reader Mode](https://tempus2016.github.io/taskmate/Pre-Reader-Mode/) for children who can't read yet, [Kiosk Mode](https://tempus2016.github.io/taskmate/Kiosk-Mode/) for a shared wall tablet (where they can claim bounties too, hide what's already done, and show the family's day or a photo slideshow while idle), a [child undo window](https://tempus2016.github.io/taskmate/Child-Undo-Window/) so they can take back a mistaken tap, an ["I'm stuck" button](https://tempus2016.github.io/taskmate/Help-Requests/) that asks a parent for help, an end-of-day [mood check-in](https://tempus2016.github.io/taskmate/Mood-Check-In/), [watch complications](https://tempus2016.github.io/taskmate/Watch-Complications/) for Apple Watch and Wear OS, [Read Aloud](https://tempus2016.github.io/taskmate/Read-Aloud/) to a media player, a [printable fridge chart](https://tempus2016.github.io/taskmate/Printable-Weekly-Chart/), each child's [photo](https://tempus2016.github.io/taskmate/Children/#child-photos) on the cards from their Home Assistant person, [custom completion sounds](https://tempus2016.github.io/taskmate/Completion-Sounds/) you can upload and pick per chore, and six [card design styles](https://tempus2016.github.io/taskmate/Card-Design-Styles/) including a high-contrast accessible theme and a clean corporate one. Cards and the panel are translated into 10 languages and support [right-to-left layouts](https://tempus2016.github.io/taskmate/Localization/).

---

## Dashboard cards

Lovelace resources register automatically on startup. Edit your dashboard → **Add Card** → search "taskmate". Or let TaskMate build them for you: **TaskMate panel → Settings → Ready-made dashboards** creates a kids', a parents' and a wall-tablet dashboard filled in with your family.

| For kids | For parents |
|----------|-------------|
| Child · Sticker Chart · Pet · Raffle · Rewards · Reward Progress · Points Display · Routine · Kiosk · Streak · Personal Bests · Badges · Bounty Board · Wishlist · Recap · Chore Auction | Approvals · Parent Dashboard · Overview · Chore Board · Activity · Points · Reorder · Penalties · Bonuses · Weekly · Graph · Leaderboard · Calendar · Family Goal · Photo Gallery |

Every card takes a `header_color` and a `card_design` option. See [Dashboard Cards](https://tempus2016.github.io/taskmate/Dashboard-Cards/) for each card's full configuration.

<p align="center">
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/childCard.png" alt="TaskMate child card" width="380">
  &nbsp;
  <img src="https://raw.githubusercontent.com/tempus2016/taskmate/main/images/overview.png" alt="TaskMate overview card" width="380">
</p>

---

## Documentation

| | |
|---|---|
| [Getting Started](https://tempus2016.github.io/taskmate/Getting-Started/) | First-time setup walkthrough |
| [Admin Panel](https://tempus2016.github.io/taskmate/Admin-Panel/) | The management hub in the HA sidebar |
| [Settings](https://tempus2016.github.io/taskmate/Settings/) | Every configurable setting in one place |
| [Dashboard Cards](https://tempus2016.github.io/taskmate/Dashboard-Cards/) | All 31 Lovelace cards and their options |
| [Services](https://tempus2016.github.io/taskmate/Services/) | Every callable service, with examples |
| [Sensor Reference](https://tempus2016.github.io/taskmate/Sensor-Reference/) | All entities and their attributes |
| [Automations](https://tempus2016.github.io/taskmate/Automations/) | Bus events, blueprints, and examples |
| [Voice Assistants](https://tempus2016.github.io/taskmate/Voice-Assistants/) | Ask Assist about chores and points |
| [Watch Complications](https://tempus2016.github.io/taskmate/Watch-Complications/) | TaskMate on Apple Watch and Wear OS |
| [Localization](https://tempus2016.github.io/taskmate/Localization/) | Supported languages and translating |
| [Troubleshooting](https://tempus2016.github.io/taskmate/Troubleshooting/) | Common issues and fixes |
| [FAQ](https://tempus2016.github.io/taskmate/FAQ/) | Frequently asked questions |

**[→ Browse the full documentation](https://tempus2016.github.io/taskmate/)** — 100+ pages, one per feature, with search.

---

## Changelog

Release notes for every version live on the [Releases page](https://github.com/tempus2016/taskmate/releases).

## Contributing

Bug reports and feature requests are welcome in [Issues](https://github.com/tempus2016/taskmate/issues); questions and ideas belong in [Discussions](https://github.com/tempus2016/taskmate/discussions). Pull requests are welcome — see [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

> Originally created by [vinnybad/choremander](https://github.com/vinnybad/choremander). This fork adds 31 Lovelace cards, an admin panel, a bonus points system, streak tracking, reward approval flow, a penalty system, and much more.
