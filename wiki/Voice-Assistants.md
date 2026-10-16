# Voice Assistants

TaskMate adds Home Assistant **conversation intents** so you can ask Assist — by voice or text — about your children's chores and points, and tick chores off.

- *"How many chores does Malia have left?"*
- *"How many stars does Alex have?"*
- *"Mark make bed as done for Malia"* (v7.0.0)
- *"What's Malia's next job?"* (v7.0.0)
- *"How close is Alex to the cinema trip?"* (v7.0.0)

---

## How It Works

There are two halves to a voice command in Home Assistant:

1. **The intent handler** — the code that answers the question. TaskMate ships five intent handlers and registers them automatically when the integration loads. Nothing to install.
2. **The trigger sentences** — the phrases HA listens for and maps to an intent. These are **not** automatic. HA's default conversation agent loads them from your config folder, so you have to copy TaskMate's example sentences in once.

The intents TaskMate provides:

| Intent | Answers or does | Example |
|--------|-----------------|---------|
| `TaskMateChoresLeft` | How many chores are still to do today | "How many chores does **Malia** have left?" |
| `TaskMatePoints` | The child's points balance | "How many stars does **Alex** have?" |
| `TaskMateCompleteChore` | *(v7.0.0)* Ticks a chore off for the child | "Mark **make bed** as done for **Malia**" |
| `TaskMateNextChore` | *(v7.0.0)* The chore the child should do next | "What's **Malia**'s next job?" |
| `TaskMateRewardProgress` | *(v7.0.0)* How many more points the child needs for a reward | "How close is **Alex** to the **cinema trip**?" |

The slots in the sentences:

| Slot | Matches |
|------|---------|
| `{child}` | Any of your children by name (case-insensitive) |
| `{chore}` | A chore due today. The closest name wins: an exact match first, then one containing what was said, then the most words in common |
| `{reward}` | A reward the child can claim, matched the same way. Leave it out ("how close is Alex to a reward") and TaskMate picks the cheapest reward the child can't afford yet |

### Completing a chore by voice

`TaskMateCompleteChore` counts as the child's own tap, never a parent's:

- Approval rules apply exactly as if the child had tapped **Done**. A chore that needs approval goes to the queue ("Done! Make bed is waiting for a grown-up to check it").
- The [linked-account rules](Parent-Access.md) decide whether the person speaking may act for that child. If not, Assist says so and nothing is completed.
- Chores that need a photo, a number ([quantity chores](Quantity-Chores.md)), a description, a timer or a team can't be finished by voice. Assist says to do that one on the card.
- A chore already done today is reported as done rather than completed again.

### Replies in your language

Replies are translated. Assist answers in the language the question was asked in, using the same translations as TaskMate's push notifications, so a German question gets a German answer.

---

## Installing the Trigger Sentences

Example sentences ship in the TaskMate repository under `custom_sentences/<language>/taskmate.yaml`, for these languages:

| Code | Language |
|------|----------|
| `en` | English |
| `da` | Danish |
| `de` | German |
| `fr` | French |
| `nb` | Norwegian Bokmål |
| `nn` | Norwegian Nynorsk |
| `pl` | Polish |
| `pt` | Portuguese |
| `pt-BR` | Portuguese (Brazil) |

Copy the file for your language into your Home Assistant config, keeping the same path. For English:

```
<config>/custom_sentences/en/taskmate.yaml
```

Then **restart Home Assistant** (or reload the conversation integration). After that, ask Assist any of the sentences above and TaskMate will answer.

> **Upgrading from before v7.0.0?** Copy the file again. Older copies used `{name}` for the child's name, but Home Assistant reserves `{name}` for device and entity names, so a sentence using it could be answered with "not aware of any device called …" instead of reaching TaskMate. The new files use `{child}` and add the three new intents. If you wrote your own sentences, change `{name}` to `{child}` in them, and rename the `name:` entry under `lists:` to `child:`. TaskMate still accepts `{name}` from an old file, so nothing breaks in the meantime.

A minimal English file looks like this:

```yaml
language: "en"
intents:
  TaskMateChoresLeft:
    data:
      - sentences:
          - "how many chores (does|has) {child} have left"
  TaskMateCompleteChore:
    data:
      - sentences:
          - "mark {chore} [as] done for {child}"
  TaskMateNextChore:
    data:
      - sentences:
          - "what('s| is) {child}'s next (job|chore)"
  TaskMateRewardProgress:
    data:
      - sentences:
          - "how close is {child} to [the] {reward}"
lists:
  child:
    wildcard: true
  chore:
    wildcard: true
  reward:
    wildcard: true
```

---

## Other Languages

For a language not in the list, copy one of the files under the matching language code, for example:

```
<config>/custom_sentences/es/taskmate.yaml
```

Then translate **only** the `sentences:` lines into that language. Leave the intent names (`TaskMateChoresLeft`, `TaskMatePoints`, `TaskMateCompleteChore`, `TaskMateNextChore`, `TaskMateRewardProgress`), the slot names (`{child}`, `{chore}`, `{reward}`) and the `lists:` keys unchanged — those are identifiers, not display text. See [Localization](Localization.md) for TaskMate's language support generally.

---

## Voice-Friendly To-do Lists

TaskMate also publishes each child's outstanding chores as a native HA to-do list (`todo.taskmate_<child name>`). Because those are standard to-do lists, voice assistants can read them out and tick items off — completing the chore — with no extra setup. This pairs well with the intents above. See [To-Do Lists](To-Do-Lists.md).

---

## See Also

- [To-Do Lists](To-Do-Lists.md) — voice-friendly chore lists per child
- [Parent Access](Parent-Access.md) — linked accounts, which decide who may complete chores for whom
- [Localization](Localization.md) — translating TaskMate
