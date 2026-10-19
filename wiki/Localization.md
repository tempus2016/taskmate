# Localization

TaskMate supports multiple languages for both the configuration UI and the Lovelace dashboard cards.

![The Settings tab](images/panel-settings.png)

---

## Supported Languages

| Language | Code | Coverage |
|----------|------|----------|
| English (GB) | `en-GB` | Full (default fallback) |
| English (US) | `en` | Full |
| Danish | `da` | Full (new in v6.0.0, contributed and reviewed by a native speaker) |
| Dutch | `nl` | Full (new in v7.1.0, community contribution) |
| French | `fr` | Full |
| German | `de` | Full |
| Norwegian Bokmål | `nb` | Full |
| Norwegian Nynorsk | `nn` | Full |
| Polish | `pl` | Full (new in v6.1.0, contributed by a native speaker) |
| Portuguese | `pt` | Full |
| Portuguese (Brazil) | `pt-BR` | Full |

---

## How It Works

TaskMate automatically uses your Home Assistant language setting. There is no separate language option within TaskMate itself.

### Changing Language

1. Go to your **HA Profile** (click your user icon in the sidebar)
2. Change **Language** to your preferred language
3. That's it. Since v6.0.0 the cards and the admin panel switch language (and direction) straight away, with no page reload

**Card titles follow your language (v6.0.0).** The points, approvals, parent dashboard, reorder and rewards cards used to save an English default title ("Manage Points", "Rewards", …) into your dashboard. A title that matches the old English default is now treated as unset, so it shows in your language. Titles you typed yourself are kept exactly as you wrote them.

### What Gets Translated

- **Config flow** — all setup screens, field labels, descriptions, and menu items
- **Dashboard cards** — all card titles, button labels, status messages, empty states, and tooltips
- **Admin panel** — all management screens, forms, and labels (v3.6.2+)
- **Service descriptions** — shown in Developer Tools when browsing services
- **Push notifications** (v6.2.0) — message text and action buttons. See [Push Notifications](#push-notifications) below

### What Does Not Get Translated

- **Your data** — child names, chore names, reward names, and descriptions are entered by you and displayed as-is
- **Points currency name** — this is set by you during setup (e.g. "Stars", "Coins") and is not translated
- **Custom notifications** — the message you write for a [custom notification](Notifications.md#custom-notifications) is sent exactly as written

---

## Push Notifications

> **New in v6.2.0**

TaskMate's push notifications are written in Home Assistant's **server** language, set under **Settings → System → General**. This is separate from the language in your user profile, which the cards and panel follow. Pushes are built on the server and go to several people at once, so they use the household's language.

What's translated:

- Every built-in notification message (approvals, reminders, badges, streaks, auctions, inspections, recaps, celebrations, …)
- The **Approve** / **Reject** buttons, the reject reply box and its "Reason (optional)" placeholder
- The "Open the TaskMate panel to approve or reject." hint sent to Telegram, email and other non-mobile backends
- Auction results, weekly digest and monthly report lines, and lists of names ("Malia, Vaiha und Alex")
- Month and weekday names in dates, for example in the monthly report, the season champion and auction dates
- The `message` of the `taskmate_celebration` event, so automations that speak it use your language
- The sample names in a **Send test** push

A regional language falls back to its base language (Swiss German `de-CH` uses German). If a message has no translation, it goes out in English, so a notification is always readable. A change of language takes effect straight away, with no restart.

Action button identifiers stay the same in every language, so existing automations and notifications already on phones keep working.

---

## Right-to-Left Languages (v6.0.0)

Every TaskMate card and the admin panel lay out **right-to-left** when Home Assistant is set to a right-to-left language such as Arabic, Hebrew, Persian or Urdu, and follow Home Assistant's own direction otherwise. There is nothing to configure.

- Text, spacing, borders and progress bars run from the right; directional icons (chevrons, undo, send) are mirrored
- Counts and number runs keep their reading order, so "3 / 5", "3-day streak" and "0 of 6 done" read correctly inside right-to-left text
- Progress rings and the points graph's time axis stay as drawn, so time still runs left to right on the graph

TaskMate doesn't ship Arabic, Hebrew, Persian or Urdu translations yet, so those languages show the layout right-to-left with English wording. The layout is ready for a translation — see below if you'd like to contribute one.

---

## Contributing Translations

Translation files are located in the repository:

- **Config flow**: `custom_components/taskmate/translations/{locale}.json`
- **Frontend cards**: `custom_components/taskmate/www/locales/{locale}.json`

To add a new language or improve an existing translation, submit a pull request to the [TaskMate repository](https://github.com/tempus2016/taskmate).

---

## Related

- [Installation](Installation.md) — initial setup
- [Getting Started](Getting-Started.md) — first-time configuration
- [Notifications](Notifications.md) — notification types and messages
