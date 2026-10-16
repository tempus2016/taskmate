# Weather Aware Chores

Outdoor chores can hide themselves when the weather is unsuitable. There is no point putting "mow the lawn" on a child's card during a downpour, and no point penalising them for not doing it.

![The Chores tab](images/panel-chores.png)

Open a chore in the **Admin Panel → Chores → Edit chore** and expand **Advanced — weather conditions**.

---

## Settings

| Setting | Effect |
|---------|--------|
| **Weather entity** | The `weather.*` entity to read. Leave empty to ignore the weather entirely. |
| **Hide when the weather is** | Any number of conditions — rainy, pouring, snowy, sleet, hail, lightning, thunderstorm, fog, windy, very windy, cloudy, severe. |
| **Minimum temperature** | Hide the chore below this. Leave empty for no limit. |
| **Maximum temperature** | Hide the chore above this. Leave empty for no limit. |
| **Maximum wind speed** | Hide the chore above this. Leave empty for no limit. |

Temperature and wind limits are read from the weather entity's `temperature` and `wind_speed` attributes, in whatever units your entity reports. TaskMate does not convert units — if your weather entity reports °F, enter your limits in °F.

Conditions are checked first, then temperature, then wind.

---

## A Rained-Off Chore Is Not a Missed Chore

The weather check sits in the same availability path as scheduling, rotation and dependencies. That means a chore hidden by the weather:

- does **not** raise a mandatory-miss review item
- does **not** break the child's streak
- does **not** count against the chore in the [Insights](Insights.md) friction report

It simply isn't due today, in the same way a Tuesday-only chore isn't due on a Wednesday.

---

## Fail-Open by Design

Anything that goes wrong leaves the chore **visible**:

- the weather entity is missing or was deleted
- its state is `unavailable` or `unknown`
- the attribute a limit needs (`temperature`, `wind_speed`) isn't present

A weather integration going offline overnight must never quietly hide the whole family's chores. The failure mode is "the child sees a chore they might not need to do", not "nobody does anything".

---

## 0 Is a Real Limit

Leave a limit **blank** to disable it. Entering `0` means zero degrees, not "off" — a common trap worth stating plainly, because "hide below 0°" and "no minimum" are very different instructions.

---

## Common Use Cases

| Chore | Setting |
|-------|---------|
| Mow the lawn | Hide on `rainy` and `pouring` |
| Wash the car | Hide below 2° |
| Put the bins out | Hide above 40 km/h wind |
| Water the plants | Hide on `rainy` — nature did it for you |
| Sweep the patio | Hide on `snowy`, hide below 0° |

---

## Related

- [Chores](Chores.md) — the chore editor and the full list of chore fields
- [Dynamic Chore Visibility](Dynamic-Chore-Visibility.md) — gating a chore on any Home Assistant entity state, not just weather
- [Chore Scheduling](Chore-Scheduling.md) — how a chore becomes due in the first place
- [Mandatory Chores](Mandatory-Chores.md) — why a weather-hidden chore never raises a miss
