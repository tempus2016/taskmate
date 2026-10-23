# Card Looks

Five ways to change how the child card (and, where noted, the kiosk card) looks and feels, without changing what it does. They work under every [card design style](Card-Design-Styles.md).

---

## Compact child card

A card option that slims each chore to a single line, so roughly twice as many fit on a phone: a smaller header, one line per chore (name, points, tick box) and smaller tick boxes. Descriptions are left out in compact mode.

Set **Density → Compact** in the card's visual editor, or in YAML:

```yaml
type: custom:taskmate-child-card
entity: sensor.taskmate_overview
child_id: a8c8376a
density: compact   # normal (default) | compact
```

---

## Seasonal themes

Optional accents that switch on by date. Turn each one on in the admin panel under **Settings → Seasonal themes**. All three are off by default.

| Season | Dates | Header | Emoji | Celebration |
|--------|-------|--------|-------|-------------|
| Halloween | 24–31 October | Orange to purple | 🎃 | Bats instead of confetti |
| Christmas | 1–26 December | Red to green | 🎄 | Snow instead of confetti |
| Summer | 21 June – 31 August | Orange to sea blue | ☀️ | Suns instead of confetti |

While a season is on and in its window, the child card and the kiosk card's child screen get:

- a **full-colour gradient header** in the season's colours (it replaces the header colour for those days),
- the season's emoji on the child's avatar and in the points pill,
- the season's celebration in place of confetti, unless the child has picked their own [done animation](#done-animation-per-child).

The overview sensor carries the active season as a `season` attribute (`halloween`, `christmas` or `summer`), present only while one is showing, so the cards don't each work out the dates.

A single card can stay plain with `seasonal: false` (the **Seasonal themes** switch in the card editor):

```yaml
type: custom:taskmate-child-card
entity: sensor.taskmate_overview
child_id: a8c8376a
seasonal: false
```

The kiosk card takes the same `seasonal: false` option.

---

## Dark care strips

The coloured strips on the child card (sick day, make it right, weekly goal, still owed, new record, appeals, screen time, boosts) switch to dark versions when Home Assistant is in dark mode. Each keeps its colour family, so a strip still means the same thing at a glance, and the text stays readable (at least WCAG AA contrast). Nothing to configure.

---

## The child's colour on their cards

The colour picked for a child in the admin panel (**Children → edit → Colour**) becomes their child card's header, the fill of their progress bars, and the tint of their confetti. On the kiosk card it colours that child's face on the picker and the header of their screen.

- A card with its own `header_color` keeps it: the card's setting wins. Clearing the colour in the card editor (**Reset**) hands the header back to the child's colour.
- A child left on **Automatic** keeps the card's usual colours.
- A light colour (a pale yellow, say) is darkened just enough for the white header text to stay readable. The **Accessible** design asks for more contrast, so it darkens a little further.

---

## Done animation per child

Each child picks what ticking off a chore feels like. Set it in the admin panel under **Children → edit → Done animation**:

| Style | What plays |
|-------|------------|
| **Confetti** | The classic, and the default |
| **Stamp** | A big "DONE!" stamp thunks onto the card |
| **Fireworks** | Bursts of colour |
| **Sticker peel** | A gold star sticker lands on the card |

It plays on the child card and the kiosk card when that child ticks a chore off. Other celebrations (birthdays, records, inspections) keep confetti, or the season's effect while one is on.

Anyone whose device asks for reduced motion (`prefers-reduced-motion`) sees no animation at all.
