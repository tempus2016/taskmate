# TaskMate voice intents

TaskMate registers Home Assistant [conversation intents](https://www.home-assistant.io/integrations/conversation/)
so you can ask Assist (voice or text) about chores and points:

- *"How many chores does Malia have left?"* → `TaskMateChoresLeft`
- *"How many stars does Alex have?"* → `TaskMatePoints`

The intent **handlers** ship with the integration and are registered
automatically. The **sentences** that trigger them are matched by HA's default
conversation agent, which loads them from your config's `custom_sentences/<lang>/`
folder.

## Install the sentences

Copy `en/taskmate.yaml` from this folder into your Home Assistant config:

```
<config>/custom_sentences/en/taskmate.yaml
```

Then restart Home Assistant (or reload the conversation integration). Ask Assist
one of the sentences above — `{name}` matches any of your children by name.

Translations: copy the file under the matching language code (e.g.
`custom_sentences/de/taskmate.yaml`) and translate the `sentences:` lines; the
intent names and `lists` keys must stay unchanged.
