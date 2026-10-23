# Getting Started

This guide walks you through setting up TaskMate for the first time after installation.

![The Children tab after first setup](images/panel-children.png)

> **Prefer a guided start?** The [Setup Wizard](Setup-Wizard.md) opens by itself the first time you open the panel, and sets up children, age-suitable chores and starter rewards in one go.

---

## Step 1 — Add the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **TaskMate** and select it
4. You will be asked to choose:
   - **Points Currency Name** — what you want to call the points (Stars, Coins, Bucks, Tokens, etc.)
   - **Points Icon** — the MDI icon used throughout the UI (default: `mdi:star`)
5. Click **Submit**

> You can change the currency name and icon later in Settings.

---

## Step 2 — Open the TaskMate Panel

After setup, **TaskMate** appears in the Home Assistant sidebar. Everything is
managed from there.

A rail down the left picks a section, and each section's pages are tabs along the top:

| Section | Contains |
|---------|----------|
| **Today** | How the day is going, and everything that needs you |
| **Family** | Children, Groups |
| **Earn** | Chores, Bounties, Auctions, Quests, Challenges, Templates |
| **Spend** | Rewards, Wishlists, Raffles |
| **Points** | Bonuses, Penalties, Badges |
| **Review** | Activity, [Insights](Insights.md), Audit |
| **Settings** | Settings, Notifications, Help & feedback |

See [Admin Panel](Admin-Panel.md#navigation) for the full tour.

> Older versions of TaskMate were configured through
> **Settings → Devices & Services → TaskMate → Configure**. That menu is gone;
> the panel replaced it.

---

## Step 3 — Add Your Children

1. Go to **Children**
2. Click **+ Add child**
3. Enter the child's name and pick an avatar
4. Save

Repeat for each child. Each child gets their own:
- Points balance
- Streak counter
- Chore completion history
- Custom chore order

---

## Step 4 — Create Some Chores

1. Go to **Chores**
2. Click **+ Add chore** (or **Bulk add** to create several at once, or
   **Create from template** to start from a built-in pack)
3. Fill in the fields:
   - **Name** — e.g. "Make Bed"
   - **Points** — how many points completing this chore earns
   - **Time of day** — Morning, Afternoon, Evening, Night, or Anytime
   - **Schedule** — specific days, a recurring interval, or a one-shot task
   - **Requires approval** — whether a parent must approve before points are awarded
4. Save

Further options — dependencies, weather conditions, visibility, bonus sub-tasks,
scheduled changes — live under the **Advanced** sections of the same dialog.

> **Tip:** Start with 3–5 chores. You can add more any time.

See [Chores](Chores.md) for a full explanation of every field.

---

## Step 5 — Create a Reward

1. Go to **Rewards**
2. Click **+ Add reward**
3. Enter a name and choose an icon
4. Set the **points cost**
5. Optionally make it a **jackpot** so assigned children pool their points
   toward a shared goal
6. Save

See [Rewards](Rewards.md) for jackpot rewards, spending caps and the claim
approval flow.

---

## Step 6 — Add Cards to Your Dashboard

1. Edit your Lovelace dashboard
2. Click **+ Add Card**
3. Search for "taskmate" — you'll see all 21 cards listed
4. Add the **Child Card** for your child's view — configure it with:
   - Entity: `sensor.taskmate_overview`
   - Child: select the child
5. Add the **Parent Dashboard Card** for the parent view

> **Tip:** Create two separate dashboards — one for kids (Child Card + Rewards Card) and one for parents (Parent Dashboard Card).

See [Dashboard Cards](Dashboard-Cards.md) for full configuration options for all cards.

---

## Step 7 — Test It

1. Open the child card on your dashboard
2. Tap a chore to complete it
3. If the chore requires approval, go to the parent dashboard and approve it
4. Watch the points balance update

---

## Finding IDs

Many card options and service calls require a `child_id` or `reward_id`. The easiest way to find these:

1. Go to **Developer Tools** → **States**
2. Find `sensor.taskmate_overview`
3. Expand the entity attributes
4. Look in the `children` array for `id` values
5. Look in the `rewards` array for reward IDs

IDs are 8-character alphanumeric strings, e.g. `a8c8376a`.

---

## Recommended Dashboard Layout

### Kids' Dashboard (Sections View)
| Section | Cards |
|---------|-------|
| Chores | Child Card (Morning), Child Card (Afternoon), Child Card (Evening) |
| Rewards & Progress | Rewards Card, Streak Card |

### Parents' Dashboard (Sections View)
| Section | Cards |
|---------|-------|
| At a Glance | Overview Card, Parent Dashboard Card |
| Points Management | Points Card, Approvals Card |
| History & Stats | Activity Card, Weekly Card, Leaderboard Card |

> **Tip:** Use Section view for both dashboards — it groups related cards visually and handles responsive layout automatically.
